from pydantic import BaseModel

class MimicOMOPOptionsType(BaseModel):
    duckdb_file_path: str = '/app/mimic_omop/mimic/mimic_omop_duckdb'
    mimic_dir: str = "/app/mimic_omop/mimic"
    vocab_dir: str = "/app/mimic_omop/vocab"
    load_mimic_vocab: bool = True
    database_code: str
    schema_name: str
    chunk_size: int = 10000

    @property
    def use_cache_db(self) -> str:
        return False