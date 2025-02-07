from pydantic import BaseModel
from typing import Optional
from enum import Enum


PATH_TO_EXTERNAL_FILES = r"dicom_etl_plugin/external"

class FlowActionType(str, Enum):
    INGEST_METADATA = "ingest_metadata"
    LOAD_VOCAB = "load_vocab"
    
class MissingPersonIDOptions(str, Enum):
    SKIP = "skip" # skip data ingestion
    USE_ID_ZERO = "use_id_zero" # use person_id = 0

class PersonPatientMapping(BaseModel):
    schema_name: str
    table_name: str
    person_id_column_name: str
    patient_id_column_name: str

class DICOMETLOptions(BaseModel):
    flow_action_type: FlowActionType
    database_code: str
    medical_imaging_schema_name: str
    cdm_schema_name: str
    vocab_schema_name: str
    to_truncate: Optional[bool] = False
    dicom_files_abs_path: Optional[str]
    upload_files: Optional[bool] = False
    missing_person_id_options: Optional[MissingPersonIDOptions] # How to handle on missing person id
    person_to_patient_mapping: Optional[PersonPatientMapping]

    @property
    def use_cache_db(self) -> str:
        return False