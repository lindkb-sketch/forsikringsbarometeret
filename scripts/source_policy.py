"""Validate issuer provenance without rejecting verified geographic PDF tables.

Gjensidige Norway uses the official investor workbook or explicitly labelled\nPrivate Norway and Commercial Norway tables in the official quarterly PDF.
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
            errors.append(f"{company} Norway {row.get('year')}Q{row.get('quarter')}: Excel sources prohibited; use official PDF tables")
        elif company=='Gjensidige' and source_type=='official_quarterly_report':
            # The country total is calculated exclusively from the two
            # explicitly named Norwegian segment tables in the issuer PDF.
            lineage=all(any(seg.get('company')=='Gjensidige'
                and seg.get('scope')=='reported_segment'
                and seg.get('segment')==segment
                and seg.get('year')==row.get('year')
                and seg.get('quarter')==row.get('quarter')
                and seg.get('period_type')==row.get('period_type')
                and seg.get('metric')==row.get('metric')
                and seg.get('source_url')==row.get('source_url')
                and seg.get('source_sha256')==row.get('source_sha256')
                and seg.get('source_section')=='General Insurance '+segment
                and isinstance(seg.get('source_page'),int)
                and seg['source_page']>0 for seg in observations)
                for segment in ('Private Norway','Commercial Norway'))
            if not (row.get('status')=='calculated'
                    and row.get('calculation') in (
                        'sum_official_norway_segments',
                        'revenue_weighted_official_norway_segments')
                    and row.get('source_section')=='General Insurance Private Norway + Commercial Norway'
                    and str(row.get('source_url','')).startswith('https://')
                    and len(str(row.get('source_sha256','')))==64
                    and lineage):
                errors.append(f"Gjensidige Norway {row.get('year')}Q{row.get('quarter')}: missing verified PDF Norway PM/BM segment provenance")
        elif company=='Tryg' and source_type=='official_quarterly_report':
            if not (isinstance(row.get('source_page'),int) and row['source_page']>0
                    and 'Norwegian general insurance' in row.get('source_section','')
                    and 'Geography' in row.get('source_section','')
                    and row.get('source_document_period')
                    and str(row.get('source_url','')).startswith('https://')):
                errors.append(f"Tryg Norway {row.get('year')}Q{row.get('quarter')}: explicitly identified PDF geography table required")
        else:
            errors.append(f"{company} Norway {row.get('year')}Q{row.get('quarter')}: verified PDF geography source required")
    return errors
