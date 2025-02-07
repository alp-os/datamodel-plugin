--liquibase formatted sql
--changeset alp:V1.0.0.0.1_create_eav_tables


CREATE TABLE dicom_image_metadata(
    metadata_id integer NOT NULL,
    metadata_date date NOT NULL,
    metadata_datetime timestamp,
    data_element_tag integer NOT NULL,
    data_element_source_name varchar(255) NOT NULL,
    data_element_source_tag varchar(255) NOT NULL,
    data_element_source_group_number varchar(255) NOT NULL,
    data_element_source_value_representation varchar(255) NOT NULL,
    is_sequence boolean NOT NULL,
    parent_sequence_id integer,
    value_as_integer integer,
    value_as_numeric numeric,
    value_as_string varchar(5000),
    value_as_datetime timestamp,
    value_as_text text,
    data_element_source_value text NOT NULL,
    image_occurrence_id integer NOT NULL
);


CREATE TABLE dicom_data_element(
    data_element_tag varchar(255) NOT NULL,
    data_element_name varchar(255) NOT NULL,
    data_element_keyword varchar(255) NOT NULL,
    value_representation varchar(255) NOT NULL,
    value_multiplicity varchar(255) NOT NULL,
    delimiter varchar(255),
    deprecated boolean
);


--rollback DROP TABLE dicom_image_metadata;
--rollback DROP TABLE dicom_data_element;