--liquibase formatted sql
--changeset alp:V1.0.0.0.2_recreate_eav_tables


DROP TABLE dicom_image_metadata CASCADE;
DROP TABLE dicom_data_element CASCADE;

-- Rename dicom_image_metadata to dicom_file_metadata
CREATE TABLE dicom_file_metadata(
    metadata_id varchar(255) NOT NULL,
    data_element_id integer,
    metadata_source_keyword varchar(255),
    metadata_source_tag varchar(20) NOT NULL,
    metadata_source_group_number varchar(20),
    metadata_source_value_representation varchar(20),
    metadata_source_value_multiplicity varchar(20),
    metadata_source_value text,
    is_sequence boolean,
    sequence_length integer,
    parent_sequence_id varchar(255),
    parent_dataset_id varchar(255),
    is_private boolean,
    private_creator varchar(255),
    sop_instance_id varchar(255),
    instance_number integer,
    image_occurrence_id integer NOT NULL,
    etl_created_datetime timestamp NOT NULL,
    etl_modified_datetime timestamp NOT NULL
);



CREATE TABLE dicom_data_element(
    data_element_id INTEGER NOT NULL,
    data_element_tag varchar(20) NOT NULL,
    data_element_name varchar(255),
    data_element_keyword varchar(255),
    value_representation varchar(20),
    value_multiplicity varchar(20),
    is_private BOOLEAN,
    is_retired BOOLEAN,
    retired_remarks VARCHAR(255),
    etl_created_datetime timestamp NOT NULL,
    etl_modified_datetime timestamp NOT NULL
);