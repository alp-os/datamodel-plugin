from flows.ner_extract_plugin.nel import *
from flows.ner_extract_plugin.types import *
from shared_utils.dao.DBDao import DBDao
import sqlalchemy as sql

import pandas as pd
import spacy
from datetime import datetime

from prefect import flow
from prefect.logging import get_run_logger

@flow(log_prints=True)
def ner_extract_plugin(options: NerExtractOptions):
    
    logger = get_run_logger()
    logger.info(f"The following spacy models are available: {spacy.info()['pipelines']}")

    logger.info("Start the connection to database")
    database_code = options.database_code
    schema_name = options.schema_name
    note_table = options.note_table
    note_nlp_table = options.note_nlp_table
    use_cache_db = options.use_cache_db

    dbdao = DBDao(use_cache_db=use_cache_db,
                  database_code=database_code, 
                  schema_name=schema_name)
    engine = dbdao.engine

    with engine.connect() as conn:
        logger.info("Loading Notes")
        note_sql = sql.text(f'SELECT note_id,note_text from {schema_name}.{note_table}')
        record = conn.execute(note_sql).fetchall()

        note_nlp_sql = sql.text(f'SELECT COUNT(*) FROM {schema_name}.{note_nlp_table}')
        count = conn.execute(note_nlp_sql).fetchall()[0][0]
        rst_df = pd.DataFrame()

        for note_id, note_text in record:
            # Two steps of add_pipeline and extract
            logger.info(f"Start to analyze note {note_id}")
            medical_ner_nel = EntityExtractorLinker()
            medical_ner_nel.add_pipeline(model_name="en_ner_bc5cdr_md", linker_name="umls")
            df1 = medical_ner_nel.extract_entities(text=note_text, confidence_threshold=0.8)

            medical_ner_nel = EntityExtractorLinker()
            medical_ner_nel.add_pipeline(model_name="en_core_med7_trf", linker_name="rxnorm")
            df2 = medical_ner_nel.extract_entities(text=note_text, confidence_threshold=0.8)
            note_df = pd.concat([df1,df2]).reset_index(drop=True)

            # logger.info(f"Complete the analysis of note {note_id}")
            # map note_df to note_nlp table
            note_df['note_id'] = note_id
            note_df['section_concept_id'] = 'N/A'
            note_df['snippet'] = note_df.apply(lambda x: note_text[x['start']-10:x['end']+10], axis=1)
            note_df['note_nlp_source_concept_id'] = 'N/A'
            note_df['nlp_system'] = note_df.apply(lambda x: '/'.join(x[['model','linker']]), axis=1)
            note_df['nlp_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            note_df['nlp_datetime'] = datetime.now().strftime("%Y-%m-%d")
            note_df['term_exists'] = 'N/A'
            note_df['term_temporal'] ='N/A'
            note_df['term_modifiers'] ='N/A'
            note_df = note_df.rename(columns={'start':'offset',
                                            'raw_text':'lexical_variant',
                                            'concept_id':'note_nlp_concept_id',
                                        })
            note_df['note_nlp_id'] = note_df.index.values + 1 + count
            
            rst_df = pd.concat([rst_df,note_df]).reset_index(drop=True)
            count += len(note_df)
            logger.info(f"Results of note_id: {note_id} for confidence_threshold=0.8 done")
    
        cols = ['note_nlp_id',
                'note_id',
                'section_concept_id',
                'snippet',
                'offset',
                'lexical_variant',
                'note_nlp_concept_id',
                'note_nlp_source_concept_id',
                'nlp_system',
                'nlp_date',
                'nlp_datetime',
                'term_exists',
                'term_temporal',
                'term_modifiers']
        rst_df[cols].to_sql(name = note_nlp_table,
                    con = engine,
                    schema = schema_name,
                    if_exists = 'append',
                    index = False,
                    chunksize = 32,
                   )