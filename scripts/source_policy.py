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
            source_ok=(str(row.get('source_url','')).lower().split('?')[0].endswith('.xlsx')
                       and str(row.get('source_document_url','')).startswith('https://')
                       and len(str(row.get('source_sha256','')))==64)
            direct=bool(row.get('source_sheet') and row.get('source_cell'))
            # A calculated Norway total has no single source cell. Verify BOTH
            # underlying official issuer workbook cells for its exact period
            # and metric instead of rejecting a fully documented calculation.
            calculated=(company=='Gjensidige' and row.get('calculation') in (
                'sum_official_norway_segments','revenue_weighted_official_norway_segments')
                and row.get('status')=='calculated')
            lineage=all(any(seg.get('company')==company
                    and seg.get('scope')=='reported_segment'
                    and seg.get('segment')==segment
                    and seg.get('year')==row.get('year') and seg.get('quarter')==row.get('quarter')
                    and seg.get('period_type')==row.get('period_type')
                    and seg.get('metric')==row.get('metric')
                    and seg.get('source_url')==row.get('source_url')
                    and seg.get('source_sha256')==row.get('source_sha256')
                    and seg.get('source_sheet') and seg.get('source_cell')
                    for seg in observations)
                    for segment in ('Private Norway','Commercial Norway')) if calculated else False
            if not (source_ok and (direct or calculated and lineage)):
                errors.append(f"{company} Norway {row.get('year')}Q{row.get('quarter')}: missing verified official XLSX cell or segment calculation provenance")
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
