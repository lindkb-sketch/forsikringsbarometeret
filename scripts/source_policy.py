"""Mandatory source routing for financial observations."""
EXCEL_NORWAY={'Tryg','Gjensidige'}

def validate_source_policy(observations):
    errors=[]
    for row in observations:
        if row.get('company') in EXCEL_NORWAY and row.get('scope')=='norway':
            if row.get('source_type') not in ('official_investor_workbook','official_excel','official_xlsx'):
                errors.append(f"{row.get('company')} Norway {row.get('year')}Q{row.get('quarter')}: XLSX source required")
    return errors
