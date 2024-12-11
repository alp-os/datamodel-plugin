## Loyalty Score Plugin

The loyalty score plugin is implemented according to [Klann JG, Henderson DW, Morris M, et al. A broadly applicable approach to enrich electronic-health-record cohorts by identifying patients with complete data: a multisite evaluation.](https://academic.oup.com/jamia/article/30/12/1985/7251531)

#### Two tables are neccessary for the implementation: 
- **coefficients.json** contains coefficients of 20 variables and intercept for loyal score calculation.
**ref**: [Lin KJ, Rosenthal GE, Murphy SN, et al. External Validation of an Algorithm to Identify Patients with High Data-Completeness in Electronic Health Records for Comparative Effectiveness Research.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7007793/)
- **concept_ls_Standard.csv** includes four columns: "concept_id_1" represents OMOP concepts matched with "concept_code" and "vocabulary_id" used to identify 20 loyalty variables. Since the OMOP CDM employs standard OMOP concepts, these concepts are further mapped to their corresponding "standard_concept" identifiers, which are used in the plugins.
The table may be updated in the future to reflect updates to OMOP concepts and to incorporate additional domain knowledge.
    **ref**: SI of [Klann JG, Henderson DW, Morris M, et al. A broadly applicable approach to enrich electronic-health-record cohorts by identifying patients with complete data: a multisite evaluation.](https://academic.oup.com/jamia/article/30/12/1985/7251531)

### Parameters explaination
#### Plugin Mode 1：calculate
```
{
  "options": {
    "mode": "calculate", # Required: calculate loyalty score or retrain model
    "indexDate": "2011-11-11", # Required: from which date to look back to compute the loyalty score
    "testRatio": 0.2, # Not used
    "schemaName": "cdmdefault", # Required: schema name of source data
    "returnYears": 0, # Not used
    "databaseCode": "alpdev_pg", # Required: database name of source data
    "lookbackYears": 2, # Not used
    "coeffTableName": null, # Optional: coefficient table used to compute loyalty score. "null" uses default coefficients from paper; or provide string, plugin will use provided table to calculate.
    "retrainCoeffTableName": null, # Not used
    "loyaltycohortTableName": "debug_1" # Required: table name to store the loyalty score.
  }
}
```
**Output table includes 20 variables and calculated loyalty score**
![alt text](image.png)

#### Plugin Mode 2：retrain
``` 
{
  "options": {
    "mode": "retrain", # Required: calculate loyalty score or retrain model
    "indexDate": "2011-11-11", # Required: from which date to look back to compute the loyalty score
    "testRatio": 0.2, # Required: split a portion of the data as testdataset
    "schemaName": "cdmdefault", # Required: schema name of source data
    "returnYears": 1, # Required: years to look back to extract return rate.
    "databaseCode": "alpdev_pg", # Required: database name of source data
    "lookbackYears": 2, # Required: years to look back to calculate the loyalty variables
    "coeffTableName": null, # Optional
    "retrainCoeffTableName": "debug_1_retrain_coeff", # Required: table name to store the retrained coefficients.
    "loyaltycohortTableName": "debug_1" # Not used
  }
}
```
**Output retrained coefficients**
![alt text](image-2.png) 
**AUC ROC metric after retrained**
![alt text](image-4.png)