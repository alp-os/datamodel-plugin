'''
Script that was used to scrape: https://dicom.nema.org/medical/dicom/current/output/chtml/part06/chapter_6.html

'''

import requests
import xml.etree.ElementTree as ET
import pandas as pd
from collections import defaultdict

# URI for DICOM Standard Part 6
xml_uri = 'https://dicom.nema.org/medical/dicom/current/source/docbook/part06/part06.xml'

# Parse the XML content
response = requests.get(xml_uri)
root = ET.fromstring(response.content)
tree = ET.ElementTree(root)

for child in root:
    if child.attrib.get('label') == '6':
        selected_node = child
   
        if selected_node is not None:
            grandchild_table = selected_node.find('.//{http://docbook.org/ns/docbook}table')
            if grandchild_table is not None:
                thead = grandchild_table.find('.//{http://docbook.org/ns/docbook}thead')
                tbody = grandchild_table.find('.//{http://docbook.org/ns/docbook}tbody')

                # Store column names
                column_names = []
                if thead is not None:
                    for tr in thead.findall('.//{http://docbook.org/ns/docbook}tr'):
                        thead_names = tr.findall('.//{http://docbook.org/ns/docbook}emphasis')
                        if thead_names is not None:
                            for name in thead_names:
                                column_names.append(name.text.strip())
                    column_names.append('Retired')
                    # Store row values
                    rows = tbody.findall('.//{http://docbook.org/ns/docbook}tr')
                    rows_data = []

                    # Loop through tbody to extract values
                    for tr in rows:
                        row_values = defaultdict(lambda: None)
                        idx = 0
                        for para in tr.findall('.//{http://docbook.org/ns/docbook}para'):
                            emphasis = para.find('.//{http://docbook.org/ns/docbook}emphasis')
                            if emphasis is not None and emphasis.text is not None:
                                row_values[column_names[idx]] = emphasis.text.strip()
                                idx += 1
                                if idx >= len(column_names):
                                    break
                            else:
                                if para is not None and para.text is not None:
                                    row_values[column_names[idx]] = para.text.strip()
                                    idx += 1
                                    if idx >= len(column_names):
                                        break

                        rows_data.append(row_values)

                    # Save the output as a DataFrame
                    df = pd.DataFrame(rows_data, columns=column_names)
                    
                    # Add extra columns required for dicom_data_element_table
                    df['Is Retired'] = df['Retired'].notna()
                    df['Is Private'] = False
                    df.to_csv('part6_attributes.csv', index=False)
        else:
            print("Node with label='6' not found.")


