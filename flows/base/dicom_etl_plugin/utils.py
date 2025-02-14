import sqlalchemy as sql
from typing import Dict, Tuple
from datetime import datetime
import os
import pandas as pd
from pydicom.tag import BaseTag

from flows.dicom_etl_plugin.types import *

def get_image_occurrence_concept_ids(modality_code: str, anatomic_site: str, vocab_dbdao) -> Tuple[int, int]:
    # get standard concept id for modality
    try:
        concept_column_names = ["concept_code", "concept_name", "concept_id", "vocabulary_id", "domain_id", "standard_concept"]
        concept_columns = vocab_dbdao.get_sqlalchemy_columns(table_name="concept", column_names=concept_column_names)
        
        # get concept name from modality code using DICOM vocabulary
        get_concept_name_stmt = sql.select(sql.distinct(concept_columns.get("concept_name"))) \
                                    .where(sql.func.upper(concept_columns.get("concept_code")) == sql.func.upper(modality_code)) \
                                    .where(concept_columns.get("vocabulary_id") == "DICOM")
        concept_name = vocab_dbdao.execute_sqlalchemy_statement(get_concept_name_stmt, vocab_dbdao.get_single_value)
        
        # get standard concept id from concept name
        get_concept_id_stmt = sql.select(concept_columns.get("concept_id")) \
                                .where(sql.func.upper(concept_columns.get("concept_name")) == sql.func.upper(concept_name)) \
                                .where(concept_columns.get("domain_id") == "Procedure") \
                                .where(concept_columns.get("standard_concept") == "S") \
                                .where(concept_columns.get("vocabulary_id") == "SNOMED")

        modality_concept_id = vocab_dbdao.execute_sqlalchemy_statement(get_concept_id_stmt, vocab_dbdao.get_single_value)
    except Exception as e:
        # Case where modality_code is not in concept or is None
        print(f"Failed to get standard concept_id for modality '{modality_code}': {e}. Defaulting to 0.")
        modality_concept_id = 0

    # get standard concept id for anatomic site
    try:
        body_part_region = "Entire " + anatomic_site.strip()
        concept_column_names = ["concept_code", "concept_name", "concept_id", "vocabulary_id", "domain_id", "standard_concept"]
        concept_columns = vocab_dbdao.get_sqlalchemy_columns(table_name="concept", column_names=concept_column_names)
        
        get_anatomic_site_concept_id_stmt = sql.select(concept_columns.get("concept_id")) \
                            .where(sql.func.upper(concept_columns.get("concept_name")) == sql.func.upper(body_part_region)) \
                            .where(concept_columns.get("domain_id") == "Spec Anatomic Site") \
                            .where(concept_columns.get("standard_concept") == "S") \
                            .where(concept_columns.get("vocabulary_id") == "SNOMED")
        anatomic_site_concept_id = vocab_dbdao.execute_sqlalchemy_statement(get_anatomic_site_concept_id_stmt, vocab_dbdao.get_single_value)
    except Exception as e:
         # Case where body_part_region is not in concept or anatomic_site is None
        print(f"Failed to get standard concept_id for anatomic_site '{anatomic_site}': {e}. Defaulting to 0.")
        anatomic_site_concept_id = 0

    return modality_concept_id, anatomic_site_concept_id


def update_vocabulary_table(dbdao, to_truncate: bool, logger):
    '''
    Add DICOM Vocabulary to Vocabulary table
    '''
    vocabulary_table = "vocabulary"
    vocab_column_names = ["vocabulary_id"]
    vocab_columns = dbdao.get_sqlalchemy_columns(table_name=vocabulary_table.casefold(), column_names=vocab_column_names)
    
    if to_truncate:
        logger.info(f"Truncating '{dbdao.schema_name}.{vocabulary_table}' table..")
        delete_conditions = [
            sql.func.upper(vocab_columns.get("vocabulary_id")) == "DICOM"
        ]
        try:
            dbdao.delete_records(vocabulary_table, delete_conditions)
            logger.info(f"Successfully truncated DICOM vocabulary from '{dbdao.schema_name}.{vocabulary_table}' table..")
        except Exception as e:
            logger.error(f"Failed to truncate DICOM vocabulary from '{dbdao.schema_name}.{vocabulary_table}' table")
            raise e
    try:
        logger.info(f"Populating '{dbdao.schema_name}.{vocabulary_table}' table..")
        values_to_insert = {
            "vocabulary_id": "DICOM",
            "vocabulary_name": "Digital Imaging and Communications in Medicine (National Electrical Manufacturers Association)",
            "vocabulary_reference": "https://www.dicomstandard.org/current", 
            "vocabulary_version": "NEMA Standard PS3", 
            "vocabulary_concept_id": 2128000000
        }
        dbdao.insert_values_into_table(vocabulary_table, values_to_insert)
    except Exception as e:
        logger.error(f"Failed to insert DICOM Vocabulary into'{dbdao.schema_name}.{vocabulary_table}' table!")
        raise e
    else:
        logger.info(f"Successfully inserted DICOM Vocabulary into '{dbdao.schema_name}.{vocabulary_table}' table!")


def update_concept_class_table(dbdao, to_truncate: bool, logger):
    '''
    Add DICOM Vocabulary to Concept Class table
    '''  
    concept_class_table = "concept_class"
    concept_class_id_col_name = ["concept_class_id"]
    concept_class_id_column = dbdao.get_sqlalchemy_columns(table_name=concept_class_table.casefold(), column_names=concept_class_id_col_name)
    
    if to_truncate:
        logger.info(f"Truncating '{dbdao.schema_name}.{concept_class_table}' table..")
        delete_conditions = [
            sql.func.upper(concept_class_id_column.get("concept_class_id")).contains("DICOM")
        ]
        try:
            dbdao.delete_records(concept_class_table, delete_conditions)
            logger.info(f"Successfully truncated DICOM vocabulary from '{dbdao.schema_name}.{concept_class_table}' table..")
        except Exception as e:
            logger.error(f"Failed to truncate DICOM vocabulary from '{dbdao.schema_name}.{concept_class_table}' table")
            raise e

    try:
        logger.info(f"Populating '{dbdao.schema_name}.{concept_class_table}' table..")
        values_to_insert = [
            {"concept_class_id": "DICOM Attributes", "concept_class_name": "DICOM Attributes", "concept_class_concept_id": 2128000002},
            {"concept_class_id": "DICOM Value Sets", "concept_class_name": "DICOM Value Sets", "concept_class_concept_id": 2128000002}
        ]
        dbdao.insert_values_into_table(concept_class_table, values_to_insert)
    except Exception as e:
        logger.error(f"Failed to insert DICOM Vocabulary into'{dbdao.schema_name}.{concept_class_table}' table!")
        raise e
    else:
        logger.info(f"Successfully inserted DICOM Vocabulary into '{dbdao.schema_name}.{concept_class_table}' table!")

   
def update_concept_table(dbdao, to_truncate: bool, logger):
    concept_table = "concept"
    concept_column_names = ["vocabulary_id"]
    concept_columns = dbdao.get_sqlalchemy_columns(table_name=concept_table.casefold(), column_names=concept_column_names)

    if to_truncate:
        logger.info(f"Truncating '{dbdao.schema_name}.{concept_table}' table..")
        delete_conditions = [
            sql.func.upper(concept_columns.get("vocabulary_id")) == "DICOM"
        ]
        try:
            dbdao.delete_records(concept_table, delete_conditions)
            logger.info(f"Successfully truncated DICOM vocabulary from '{dbdao.schema_name}.{concept_table}' table..")
        except Exception as e:
            logger.error(f"Failed to truncate DICOM vocabulary from '{dbdao.schema_name}.{concept_table}' table")
            raise e

    logger.info(f"Populating '{dbdao.schema_name}.{concept_table}' table..")
    try:
        concept_df = pd.read_csv(f"{PATH_TO_EXTERNAL_FILES}/omop_table_staging.csv")
        
        # Adjust its data types
        concept_df['valid_end_date'] = pd.to_datetime('1993-01-01')
        concept_df['valid_start_date'] = pd.to_datetime('2099-12-31')
        concept_df['standard_concept'] = ' '
        concept_df['invalid_reason'] = ' '

        # make sure string values have datatype of str
        varchar_columns = ['concept_name', 'domain_id', 'vocabulary_id', 'concept_class_id', 'standard_concept', 'concept_code', 'invalid_reason']
        for col in varchar_columns:
            concept_df[col] = concept_df[col].astype(str)

        # handle NULLs for SQL 
        concept_df = concept_df.where(pd.notnull(concept_df), None)

        concept_df.to_sql(
            name=concept_table, 
            con=dbdao.engine,
            schema=dbdao.schema_name,
            if_exists="append",
            index=False
        )
    except Exception as e:
        logger.error(f"Failed to insert DICOM Concepts into'{dbdao.schema_name}.{concept_table}' table!")
        raise e
    else:
        logger.info(f"Successfully inserted DICOM Concepts into '{dbdao.schema_name}.{concept_table}' table!")
        
        
def update_dicom_data_element_table(dbdao, to_truncate:bool, logger):
    data_element_table_name = "dicom_data_element"
    column_names = ["data_element_tag", "data_element_id"]
    data_element_columns = dbdao.get_sqlalchemy_columns(table_name=data_element_table_name, column_names=column_names)

    if to_truncate:
        logger.info(f"Truncating '{dbdao.schema_name}.{data_element_table_name}' table..")
        delete_conditions = [
            data_element_columns.get("data_element_id") > 0
        ]
        try:
            dbdao.delete_records(data_element_table_name, delete_conditions)
            logger.info(f"Successfully truncated '{dbdao.schema_name}.{data_element_table_name}' table..")
        except Exception as e:
            logger.error(f"Failed to truncate '{dbdao.schema_name}.{data_element_table_name}' table")
            raise e

    try:
        logger.info(f"Populating '{dbdao.schema_name}.{data_element_table_name}' table from csv..")
        df = pd.read_csv(f"{PATH_TO_EXTERNAL_FILES}/part6_attributes.csv")
        
        column_mapping = {
            "Tag": "data_element_tag",
            "Name": "data_element_name",
            "Keyword": "data_element_keyword",
            "VR": "value_representation",
            "VM": "value_multiplicity",
            "Retired": "retired_remarks",
            "Is Retired": "is_retired",
            "Is Private": "is_private"
        }
        
        df = df.rename(columns=column_mapping)
        df['data_element_id'] = range(1, len(df)+1)
        df['etl_created_datetime'] = datetime.now()
        df['etl_modified_datetime'] = datetime.now()
        
        df.to_sql(
            name=data_element_table_name,
            con=dbdao.engine,
            schema=dbdao.schema_name,
            if_exists="append",
            index=False
        )
    except Exception as e:
        logger.error(f"Failed to populate '{dbdao.schema_name}.{data_element_table_name}' table!")
        raise e
    else:
        logger.info(f"Successfully populated '{dbdao.schema_name}.{data_element_table_name}' table!")


def check_none_attributes(**kwargs):
    none_attrs = [key for key, value in kwargs.items() if value is None]
    if none_attrs:
        raise Exception(f"These data elements are not found/do not have a value in the DICOM file: {', '.join(none_attrs)}")


def convert_dicom_dates(date_string: str) -> datetime.date:
    # DICOM DA VR format is YYYYMMDD
    return datetime.strptime(date_string, "%Y%m%d").date()


def impute_birth_year(age_str: str, study_date: str) -> int:
    study_date_year = int(study_date[0:4])
    age_value = int(age_str[:-1])
    age_unit = age_str[-1]
    
    if age_unit == "M":
        age_in_years = age_value/12
    elif age_unit == "W":
        age_in_years = age_value/52
    elif age_unit == "Y":
        age_in_years = age_value
    else:
        raise ValueError(f"Invalid age string '{age_str}'")
    return study_date_year - round(age_in_years)
    

def convert_tag_to_tuple(tag: BaseTag) -> str:
    str_tuple =  f"({tag.group:04X},{tag.element:04X})"
    return str_tuple


def get_person_id(dbdao, patient_id: str, missing_person_id_option, mapping) -> int:
    table_name = mapping.table_name
    mapped_person_id = mapping.person_id_column_name
    mapped_patient_id = mapping.patient_id_column_name
    
    column_names = [mapped_person_id, mapped_patient_id]
    
    columns = dbdao.get_sqlalchemy_columns(table_name=table_name, column_names=column_names)
    
    sql_statement = sql.select(columns.get(mapped_person_id)) \
                        .where(sql.func.upper(columns.get(mapped_patient_id)) == sql.func.upper(patient_id))

    try:
        person_id = dbdao.execute_sqlalchemy_statement(sql_statement, callback=dbdao.get_single_value)
    except Exception as e:
        print(f"Failed to get matching person_id for patient_id '{patient_id}': {e}")
        
        match missing_person_id_option:
            case MissingPersonIDOptions.SKIP:
                raise Exception(f"Failed to get person_id for patient_id '{patient_id}'. Skipping data ingestion..")
            case MissingPersonIDOptions.USE_ID_ZERO:
                print(f"Defaulting to person_id '0' due to missing person_id for patient_id '{patient_id}'")
                return 0
    else:
        # Matching person_id for patient_id found
        return person_id

# Todo: standardize values map study description to procedure_concept_id with Athena
def insert_procedure_occurence_table(dbdao, person_id: int, study_date: str, study_description: str) -> int:
    po_table_name = "procedure_occurrence"
    new_po_id = dbdao.get_next_record_id(po_table_name, "procedure_occurrence_id")
    print(f"Inserting new procedure occurrence record with procedure_occurrence_id of '{new_po_id}'")
    new_po_record = {
            "procedure_occurrence_id": new_po_id,
            "person_id": person_id,
            "procedure_concept_id": 0,
            "procedure_date": convert_dicom_dates(study_date) if study_date else study_date,
            "procedure_type_concept_id": 32817, # EHR
            "procedure_source_value": study_description
        }
    
    dbdao.insert_values_into_table(po_table_name, new_po_record)
    print(f"New procedure occurrence record inserted with procedure_occurrence_id of '{new_po_id}'")
    return new_po_id


def insert_image_occurrence_table(vocab_dbdao, mi_dbdao,
                                  modality_code: str, body_part_examined: str,
                                  study_uid: str, series_uid: str, acquisition_date: str,
                                  person_id: int = 0, procedure_occurrence_id: int = 0) -> int:
    
    table_name = "image_occurrence"

    modality_concept_id, anatomic_site_concept_id = get_image_occurrence_concept_ids(modality_code, body_part_examined, vocab_dbdao)

    new_image_occurrence__id = mi_dbdao.get_next_record_id(table_name, "image_occurrence_id")

    image_occurrence_date = convert_dicom_dates(acquisition_date)
    
    values_to_insert = {
    "image_occurrence_id": new_image_occurrence__id,
    "person_id": person_id,
    "procedure_occurrence_id": procedure_occurrence_id,
    "anatomic_site_concept_id": anatomic_site_concept_id,
    "image_occurrence_date": image_occurrence_date,
    "image_study_uid": str(study_uid),
    "image_series_uid": str(series_uid),
    "modality_concept_id":  modality_concept_id
    }

    mi_dbdao.insert_values_into_table(table_name, values_to_insert)
    print(f"New image occurrence record inserted with procedure_occurrence_id of '{new_image_occurrence__id}'")
    return new_image_occurrence__id
    
    
def insert_data_element_table(dbdao, tag: str, name: str, keyword: str, 
                              value_representation: str, is_private: bool) -> int:

    table_name = "dicom_data_element"
    new_data_element_id = dbdao.get_next_record_id(table_name, "data_element_id")
    
    new_data_element_record = {
        "data_element_id": new_data_element_id,
        "data_element_tag": tag,
        "data_element_name": name,
        "data_element_keyword": keyword,
        "value_representation": value_representation,
        "is_private": is_private,
        "etl_created_datetime": datetime.now(),
        "etl_modified_datetime": datetime.now()
    }
    dbdao.insert_values_into_table(table_name, new_data_element_record)

    return new_data_element_id


def get_data_element_id(dbdao, tag: str, name: str, 
                        keyword: str, value_representation: str, 
                        is_private: bool) -> int:
    
    table_name = "dicom_data_element"
    column_names = ["data_element_id", "data_element_tag"]
    sqlalchemy_columns = dbdao.get_sqlalchemy_columns(table_name=table_name, column_names=column_names)
        
    # Get data_element_id through matching data_element_tag
    sql_statement = sql.select(sqlalchemy_columns.get("data_element_id")) \
                        .where(sqlalchemy_columns.get("data_element_tag") == tag)
                        
    try:
        res = dbdao.execute_sqlalchemy_statement(sql_statement, callback=dbdao.get_single_value)
    except Exception as e:
        #print(f"Failed to get matching data_element_id for tag '{tag}': {e}")
        new_data_element_id = insert_data_element_table(dbdao, tag, name, keyword, value_representation, is_private)
        #print(f"'{tag}' inserted into '{table_name}' table with data_element_id '{new_data_element_id}'")
        return new_data_element_id
    else: 
        return res