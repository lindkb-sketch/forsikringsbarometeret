"""Validate issuer provenance without rejecting verified geographic PDF tables.

Gjensidige Norway prefers its detailed official investor workbook, with\na verified, explicitly labelled official PDF segment-table fallback.
Tryg Norway can use an explicitly named Norway geography table in an official
quarterly PDF; neither group-wide nor unlabelled figures qualify.
"""
def validate_source_policy(observations):
    errors=[]
    for row in observations:
        company=row.get('company')
        if row.get('scope')!='norway' or company not in ('Tryg','Gjensidige'):
            continue
        source_type=row.get('source_type')
        if source_type in ('official_investor_tables','official_investor_workbook','official_excel','official_xlsx'):
            if not (str(row.get('source_url','')).lower().split('?')[0].endswith('.xlsx')
                    and row.get('source_sheet') and row.get('source_cell')
                    and row.get('source_document_url') and row.get('source_sha256')):
                errors.append(f"{company} Norway {row.get('year')}Q{row.get('quarter')}: missing official XLSX cell provenance")
        elif company=='Gjensidige' and source_type=='official_quarterly_report':
            # Fallback is accepted only for the two explicitly labelled
            # Norway segments, with a PDF page and SHA-256 source fingerprint.
            # Never accept a group number or an unidentified geography.
            if not (str(row.get('source_url','')).startswith('https://')
                    and isinstance(row.get('source_page'),int) and row['source_page']>0
                    and len(str(row.get('source_sha256','')))==64
                    and row.get('source_section')=='General Insurance Private Norway + Commercial Norway'
                    and row.get('calculation') in (
                        'sum_official_norway_segments',
                        'revenue_weighted_official_norway_segments')):
                errors.append(f"Gjensidige Norway {row.get('year')}Q{row.get('quarter')}: independently verified official PDF segment tables required")
        elif company=='Tryg' and source_type=='official_quarterly_report':
            if not (isinstance(row.get('source_page'),int) and row['source_page']>0
                    and 'Norwegian general insurance' in row.get('source_section','')
                    and 'Geography' in row.get('source_section','')
                    and row.get('source_document_period')
                    and str(row.get('source_url','')).startswith('https://')):
                errors.append(f"Tryg Norway {row.get('year')}Q{row.get('quarter')}: explicitly identified PDF geography table required")
        else:
            errors.append(f"{company} Norway {row.get('year')}Q{row.get('quarter')}: verified geography workbook required")
    return errors
