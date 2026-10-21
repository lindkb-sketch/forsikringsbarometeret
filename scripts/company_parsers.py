"""Company-specific mapping rules. Conservative: ambiguous cells never publish."""
import re
ALIASES={
"Fremtind":{"insurance_revenue":r"inntekter fra forsikringstjenester","insurance_service_result":r"resultat fra forsikringstjenester","combined_ratio":r"combined ratio"},
"Gjensidige":{"insurance_revenue":r"insurance revenue|forsikringsinntekter","insurance_service_result":r"insurance service result|forsikringsresultat","combined_ratio":r"combined ratio"},
"Tryg":{"insurance_revenue":r"insurance revenue","insurance_service_result":r"insurance service result|technical result","combined_ratio":r"combined ratio"},
"Sampo":{"insurance_revenue":r"insurance revenue,? net","insurance_service_result":r"underwriting result","combined_ratio":r"combined ratio"},
"Frende":{"insurance_revenue":r"forsikringsinntekter|inntekter fra forsikringstjenester","insurance_service_result":r"forsikringsresultat|resultat fra forsikringstjenester","combined_ratio":r"combined ratio"},
"Protector":{"insurance_revenue":r"insurance revenue","insurance_service_result":r"insurance service result","combined_ratio":r"combined ratio"},
"Storebrand":{"insurance_revenue":r"insurance revenue","insurance_service_result":r"insurance service result","combined_ratio":r"combined ratio","return_on_equity":r"return on equity|roe"}
}
def identify_metrics(company,text):
    if company not in ALIASES:raise ValueError("Unknown company")
    return [metric for metric,pattern in ALIASES[company].items() if re.search(r"(?<!\\w)(?:"+pattern+r")(?!\\w)",text,re.I)]
def stage_rows(company,extraction):
    """Label relevant rows; do not infer column period or scope."""
    staged=[]
    for page in extraction.get("pages_with_financial_terms",[]):
        for table in page.get("tables",[]):
            for row in table or []:
                if not row or not row[0]:continue
                metrics=identify_metrics(company,str(row[0]))
                for metric in metrics:
                    staged.append({"company":company,"metric":metric,"page":page["page"],"raw_row":row,"status":"needs_scope_period_column_review"})
    return staged
