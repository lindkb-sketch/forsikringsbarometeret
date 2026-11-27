"""Causal market commentary from verified original results documents.

Exact report/slide headings and corroborating phrases establish scope and
period. Store the actual matching fragments, not just a theme label. Unknown
layouts fail closed. No web/news/statistics source may enter this module.
"""
import re

def explain(company,y,q,doc,texts):
    if doc.get('document_type') not in ('quarterly_report','results_presentation') or doc.get('status')!='verified_document' or not doc.get('issuer_verified') or not doc.get('period_verified'):return []
    if not re.fullmatch(r'[0-9a-f]{64}',doc.get('source_sha256','')) or not doc.get('url','').startswith('https://'):return []
    period=f'Q{q} {y}';out=[];deck=doc['document_type']=='results_presentation'
    source_type='official_results_presentation' if deck else 'official_quarterly_report'
    def group(m):return ['group/'+m,'group/all'] if m!='all' else ['group/all']
    def norway(m):return ['norway/'+m,'norway/all'] if m!='all' else ['norway/all']
    def both(m):return group(m)+norway(m)
    def amount(x):return ('%g'%float(x.replace(',','').replace(' ',''))).replace('.',',')
    def decimal(x):return ('%g'%float(x.replace(',','.'))).replace('.',',')
    def fmt(m,i=0,j=1):return decimal(m[i][j])
    last_gj=None
    for page,raw in enumerate(texts,1):
        lines=[' '.join(l.replace('\u00ad','').replace('’',"'").split()) for l in raw.splitlines() if l.strip()]
        t=' '.join(lines);head=' '.join(lines[:5])
        def has(p):return re.search(p,t,re.I)
        def add(theme,topic,views,mode,priority,patterns,message,kind=''):
            matches=[has(p) for p in patterns]
            if not all(matches):return
            msg=message(matches) if callable(message) else message
            if not msg:return
            for pt in ('quarter','ytd') if q==1 else (mode,):
                out.append(dict(company=company,period=period,source_document_period=period,period_type=pt,views=views,
                    theme=theme,driver=topic,topic=topic,category=kind,priority=priority,text=msg,
                    evidence=' | '.join(m.group(0) for m in matches),source_type=source_type,
                    source_url=doc['url'],source_sha256=doc['source_sha256'],source_page=page,supplemental_document=True))
        if deck:
            # The verified current deck cover anchors results narrative slides,
            # but a clearly historical slide or a forecast is not a Q result.
            if re.search(r'\b(?:appendix|outlook|guidance|consensus|forecast)\b',' '.join(lines[:2]),re.I):continue
            if company=='Sampo' and re.search(r'^(?:Palette\s+)?Private UK:\s*Capturing growth with disciplined underwriting',head,re.I):
                add('growth_explanation','uk_volume',group('all'),'quarter',67,
                    [r'LCP growth of [\d.,]+%\s+quarter-on-quarter and ([\d.,]+)%\s+year-on-year'],
                    lambda m:'Britisk privatforsikring viser et konkret volumbidrag: den rapporterte LCP-bestanden har økt '+fmt(m)+' % på ett år.','volume')
            if company=='Protector' and re.search(rf'^Volume update\s+Q{q}:\s*GWP growth',head,re.I):
                add('growth_explanation','currency_gwp',group('bm'),'quarter',68,
                    [rf'Q{q}:\s*GWP growth at ([\d.,]+)%\s*\|\s*([\d.,]+)% in local currencies \(LCY\)'],
                    lambda m:'Valuta påvirker også vekstbildet: i en kommersiell portefølje økte bruttopremiene '+fmt(m)+' % i rapporteringsvaluta, mot '+fmt(m,0,2)+' % i lokal valuta.','currency')
            if company=='Storebrand' and has(r'\bInsurance\b') and has(r'\bPortfolio premiums\b') and has(r'\bKey takeaways\b'):
                add('growth_explanation','retail_growth',both('all'),'quarter',62,[r'Strong growth and result development within Retail'],
                    'Privatkundeporteføljen rapporteres som et område med sterk vekst og bedre resultatutvikling.','volume')
            if company=='Tryg' and has(r'New motor partnerships with attractive brands support growth ambitions in Sweden and Norway'):
                add('event_explanation','motor_distribution',group('all'),'quarter',73,
                    [r'New motor partnerships with attractive brands support growth ambitions in Sweden and Norway'],
                    'Nye bilforsikringspartnerskap i Sverige og Norge skal understøtte videre salg. Bidraget til kvartalets inntekter er ikke tallfestet.')
            continue
        if company=='Fremtind':
            if 'Styrets beretning' in t and 'Resultatutvikling i kvartalet' in t:
                views=both('all')
                price=r'Veksten er hovedsakelig drevet av premiejusteringer'
                for mode in ('quarter','ytd'):
                    if mode=='ytd' and ('Resultatutvikling hittil i år' not in t or len(re.findall(price,t,re.I))<2):continue
                    add('growth_explanation','premium_adjustment',views+both('pm')+both('bm'),mode,86,[price],
                        'Premiejusteringer er en sentral driver i den rapporterte porteføljen.','price')
                freq=r'lavere skadefrekvenser på bil og'
                for mode in ('quarter','ytd'):
                    if mode=='ytd' and ('Resultatutvikling hittil i år' not in t or not has(r'lavere skadefrekvenser.{0,120}på bil og næringsbygg')):continue
                    add('loss_explanation','motor_property_frequency',views,mode,100,
                        [r'økte premieinntekter',freq,r'næringsbygg'],
                        'Økte premieinntekter og færre skader på bil og næringsbygg forklarer en vesentlig del av bedringen i skadeprosenten.','frequency')
                add('cost_explanation','expense_reclassification',views,'quarter',100,
                    [r'omklassifisering av rentekostnader lån fra',r'forsikringsrelaterte kostnader til andre kostnader',r'samt høyere inntekter'],
                    'I en norsk portefølje skyldes lavere kostnadsprosent både økte inntekter og at lånerenter er flyttet ut av forsikringskostnadene; det er ikke bare en effektiviseringsgevinst.')
                add('cost_explanation','personnel_expenses',views,'ytd',100,
                    [r'prosentpoeng skyldes hovedsakelig lavere personalkostnader',r'økte premieinntekter, samt omklassifisering av rentekostnader lån'],
                    'Lavere personalkostnader og høyere premieinntekter har bidratt til lavere kostnadsprosent hittil i år, sammen med omklassifisering av lånerenter.')
                for mode in ('quarter','ytd'):
                    add('event_explanation','named_fire',views,mode,105,
                        [r'Brannen i ([A-ZÆØÅ][\w-]+) utgjorde ([\d ]+) millioner kroner av',r'kvartalets netto storskader'],
                        lambda m:('I siste kvartal: ' if mode=='ytd' else '')+'Brannen i '+m[0][1]+' belastet netto storskader med '+amount(m[0][2])+' mill. kroner, samtidig som færre løpende skader bidro positivt i porteføljen.')
                add('event_explanation','weather_offset',views,'quarter',75,
                    [r'I kvartalet utgjorde netto værskader ([\d ]+) millioner',r'det er en reduksjon på ([\d ]+) millioner kroner fra tilsvarende kvartal'],
                    lambda m:'I samme portefølje var netto værskader '+amount(m[0][1])+' mill. kroner, '+amount(m[1][1])+' mill. lavere enn i fjor. Det dempet den samlede skadebelastningen.')
                add('event_explanation','large_loss_ytd',views,'ytd',85,
                    [r'storskader på totalt ([\d ]+) millioner kroner, det er en økning på ([\d ]+) millioner',r'Økningen skyldes flere brannskader'],
                    lambda m:'Netto storskader hittil i år var '+amount(m[0][1])+' mill. kroner, opp '+amount(m[0][2])+' mill., som følge av flere brannskader.')
            if has(r'Segment Privatmarkedet og Bedriftsmarkedet|Segmentresultater'):
                for mode in ('quarter','ytd'):
                    pm=r'Forbedringen i combined ratio for Privatmarkedet skyldes lavere' if mode=='quarter' else r'Forbedringen i combined ratio for Privatmarkedet hittil i år skyldes lavere'
                    add('loss_explanation','motor_frequency',both('pm'),mode,102,[pm,r'skadefrekvens innen bilforsikring'],
                        'Lavere skadefrekvens på bil og høyere premier bedrer privatlønnsomheten, ifølge den norske rapporteringen.','frequency')
                    bm=r'Combined ratio for Bedriftsmarkedet er i kvartalet isolert preget av lavere' if mode=='quarter' else r'ratio for Bedriftsmarkedet er hittil i år preget av lavere skadefrekvens'
                    add('loss_explanation','commercial_frequency',both('bm'),mode,98,[bm,r'næringsbygg- og bilforsikring'],
                        'Lavere skadefrekvens på næringsbygg og bil trekker i riktig retning i bedriftsporteføljen.','frequency')
                    prefix='I siste kvartal: ' if mode=='ytd' else ''
                    add('event_explanation','pm_fire',both('pm'),mode,108,
                        [r'Privatmarkedet utgjorde ([\d ]+) millioner kroner i kvartalet, hvorav ([\d ]+) millioner',r'kroner kommer fra brannen i ([A-ZÆØÅ][\w-]+)',r'Privatmarkedet øker skadeprosenten med ([\d,]+) prosentpoeng'],
                        lambda m:prefix+'Brannen i '+m[1][1]+' utgjorde '+amount(m[0][2])+' mill. kroner i privatporteføljen. Netto storskader på '+amount(m[0][1])+' mill. belastet skadeprosenten med '+fmt(m,2)+' prosentpoeng.')
                    add('event_explanation','bm_large_loss',both('bm'),mode,107,
                        [r'Bedriftsmarkedet utgjorde ([\d ]+) millioner kroner i kvartalet',r'Bedriftsmarkedet med ([\d,]+) prosentpoeng i kvartalet'],
                        lambda m:prefix+'Netto storskader på '+amount(m[0][1])+' mill. kroner belastet CR i en bedriftsportefølje med '+fmt(m,1)+' prosentpoeng. Det forklarer hvorfor bedre løpende skadefrekvens ikke nødvendigvis gir lavere rapportert CR.')
                add('event_explanation','realised_synergies',both('all'),'ytd',77,
                    [r'fusjonssynergier følger planen',r'realisert synergieffekter på ([\d ]+) millioner kroner'],
                    lambda m:'Integrasjonen av Eika fortsetter, med rapporterte realiserte synergier på '+amount(m[1][1])+' mill. kroner. Synergimålet må ikke forveksles med kostnadsbesparelsen i kvartalet.')
        elif company=='Gjensidige':
            named=next((s for s in ('Private','Commercial') if any(re.fullmatch(r'General Insurance '+s+r'(?: \(change in local currency\))?',l,re.I) for l in lines)),None)
            if named and 'Development during the quarter' in t:
                seg,mode=named,'quarter';last_gj=(page,seg)
            elif last_gj and page==last_gj[0]+1 and 'Year-to-date development' in t and has(r'\bNOK millions\b'):
                seg,mode=last_gj[1],'ytd'
            else:continue
            if seg=='Private':
                add('growth_explanation','pm_price_volume',both('pm'),mode,101,
                    [r'(?:driven by price increases and higher volumes|by price increases and higher volumes for the main)',r'(?:number of customers increased|customers increased, and Gjensidige maintained)'],
                    'Privatveksten støttes både av prisøkninger og økte forsikringsvolumer, samtidig som kundebestanden vokser.','volume')
                if mode=='quarter':
                    add('growth_explanation','pm_product_volumes',both('pm'),mode,104,
                        [r'price increases and higher volumes',r'for property, accident and health and travel insurance',r'Volumes in motor insurance were stable'],
                        'Rapporteringen viser at privatveksten støttes av prisøkninger og økte volumer innen eiendom, person- og reiseforsikring, mens bilvolumet er mer stabilt.','volume')
                    add('event_explanation','revenue_recognition_base',both('pm'),mode,98,
                        [r'home seller insurance resulted in a non-recurring',r'positive effect of NOK ([\d.,]+) million on insurance',r'increased by ([\d.,]+) per cent, or ([\d.,]+) per cent adjusted for'],
                        lambda m:'En engangsinntekt på '+fmt(m,1)+' mill. kroner fra boligselgerforsikring i sammenligningskvartalet demper rapportert vekst. I den norske privatporteføljen er veksten '+fmt(m,2,2)+' % justert for effekten, mot '+fmt(m,2)+' % rapportert.')
                if mode=='ytd':
                    add('event_explanation','revenue_recognition_base',group('pm'),mode,100,
                        [r'Insurance revenue increased by ([\d.,]+) per cent, or ([\d.,]+)',r'per cent adjusted for the non-recurring effect in the',r'third quarter of '+str(y-1)],
                        lambda m:'Fjorårets engangseffekt fra inntektsføring demper sammenlignbar vekst også hittil i år: i det nordiske privatsegmentet var veksten '+fmt(m,0,2)+' % justert, mot '+fmt(m)+' % rapportert.')
                    add('event_explanation','revenue_recognition_base',norway('pm'),mode,100,
                        [r'In Norway, insurance revenue',r'increased by ([\d.,]+) per cent, or ([\d.,]+) per cent adjusted for',r"last year's non-recurring effect"],
                        lambda m:'Fjorårets engangseffekt fra inntektsføring demper veksten hittil i år. I norsk privatforsikring var veksten '+fmt(m,1,2)+' % justert, mot '+fmt(m,1)+' % rapportert.')
                    add('loss_explanation','private_runoff_ytd',group('pm'),mode,93,[r'Higher run-off gains also contributed positively',r'The loss ratio improved'],
                        'Avviklingsgevinster fra tidligere skadeår har også bidratt til lavere skadeprosent hittil i år.','temporary')
                    add('loss_explanation','private_weather_ytd',both('pm'),mode,94,
                        [r'by [\d.,]+ percentage points, mainly driven by motor',r'insurance, reflecting pricing measures and favourable',r'weather conditions during the first two quarters'],
                        'I norsk privatforsikring har gunstig vær i første halvår, sammen med prisgrep innen bil, styrket skadelønnsomheten hittil i år.','weather')
                add('loss_explanation','motor_pricing',both('pm'),mode,96,
                    [r'underlying frequency loss ratio improved',r'pricing measures in motor insurance|insurance, reflecting pricing measures and favourable'],
                    'Prisgrep innen bilforsikring gir høyere underliggende skadelønnsomhet; bedringen skyldes dermed ikke bare gunstige enkeltskader.','pricing')
                add('cost_explanation','revenue_scale_efficiency',group('pm'),mode,99,
                    [r'The cost ratio improved by [\d.,]+ percentage points',r'primarily reflecting revenue growth',r'(?:strict cost discipline|cost efficiency)'],
                    'I privatsegmentet bedrer veksten kostnadsdekningen, mens effektivisering og stram kostnadsstyring holder igjen kostnadsveksten.')
                add('cost_explanation','private_cost_context',norway('pm'),mode,78,
                    [r'The cost ratio improved by [\d.,]+ percentage points',r'primarily reflecting revenue growth',r'(?:strict cost discipline|cost efficiency)'],
                    'I den samlede privatsegmentrapporten forklares kostnadsbedringen med bedre kostnadsdekning fra inntektsvekst og kostnadsdisiplin; bidragene er ikke separat tallfestet for Norge.')
            else:
                add('growth_explanation','bm_selectivity',both('bm'),mode,105,
                    [r'price increases for all products',r'prioriti[sz]ation of profitability over growth|profitability over growth and the termination of',r'agreements with fire mutuals'],
                    'Bedriftsveksten dempes av mer selektiv risikoutvelgelse og avsluttede brannkasseavtaler, som motvirker prisøkningene.','restraint')
                add('loss_explanation','commercial_pricing_selection',both('bm'),mode,101,
                    [r'underlying frequency loss ratio improved',r'better risk selection',r'effective pricing measures|pricing measures'],
                    'Prisjusteringer og bedre risikoutvelgelse styrker lønnsomheten innen blant annet bil-, eiendoms- og sjøforsikring.','pricing')
                add('loss_explanation','mid_sized_claims',group('bm'),mode,87,
                    [r'A lower frequency of mid-sized',r'claims contributed positively'],
                    'Færre mellomstore skader bidrar også til bedre underliggende skadeprosent.','frequency')
                if mode=='ytd':
                    add('loss_explanation','commercial_ytd_runoff',group('bm'),mode,90,
                        [r'ratio and lower large losses. Lower run-off gains',r'contributed negatively'],
                        'Lavere storskader bedrer skaderesultatet hittil i år, men lavere avviklingsgevinster trekker i motsatt retning.','temporary')
                    add('loss_explanation','commercial_ytd_weather',both('bm'),mode,92,
                        [r'pricing measures, better risk selection and favourable',r'weather conditions in the first two quarters'],
                        'Gunstige værforhold tidligere i året har forsterket effekten av prisjusteringer og risikoutvelgelse i norsk bedriftsforsikring.','weather')
                    add('event_explanation','fire_mutual_exit',both('bm'),mode,89,[r'termination of agreements with fire mutuals',r'customer retention rate declined slightly'],
                        'Avsluttede brannkasseavtaler påvirker volum og kundelojalitet i bedriftsporteføljen, men reflekterer en bevisst prioritering av lønnsom vekst.')
        elif company=='Tryg':
            private=bool(has(r'Key figures\s*[-–]\s*Private'))
            commercial=bool(has(r'Key figures\s*[-–]\s*Commercial'))
            if (private or commercial) and has(rf'Results Q{q} {y}'):
                views=group('pm' if private else 'bm')
                if private:
                    add('growth_explanation','pm_inflation_moderation',views,'quarter',81,
                        [r'growth was positively impacted by portfolio',r'growth in selected segments',r'profitability initiatives to balance',r'impact of these initiatives'],
                        'Porteføljevekst og prisgrep for å møte skadeinflasjon støtter privatinntektene, men effekten av prisgrepene avtar når inflasjonspresset dempes.','price')
                    add('loss_explanation','pm_weather_runoff',views,'quarter',93,
                        [r'Weather claims of ([\d.,]+)% \(([\d.,]+)%\)',r'benign',r'Run-off'],
                        lambda m:'Gunstige værforhold bidro også til lavere skader; i en nordisk privatportefølje falt værskadeandelen fra '+fmt(m,0,2)+' til '+fmt(m)+' % av inntektene.' if float(m[0][1].replace(',','.'))<float(m[0][2].replace(',','.')) else '','weather')
                    add('loss_explanation','pm_weather_ytd',views,'ytd',92,
                        [r'favourable weather claims experience of ([\d.,]+)%',r'higher run-off level'],
                        'Lavere værskader og høyere avviklingsgevinster har støttet den nordiske privatlønnsomheten hittil i år.','weather')
                else:
                    for mode in ('quarter','ytd'):
                        add('growth_explanation','bm_churn_renewals',views,mode,97,
                            [r'less than satisfactory renewal',r'churn of a few large clients',r'SME portfolio developed favourably'],
                            'Svakere fornyelser ved årsskiftet og tap av store bedriftskunder bremser veksten, mens SMB-porteføljen utvikler seg bedre enn storkundesegmentet.','restraint')
                    add('loss_explanation','runoff_offset',views,'quarter',97,
                        [r'lower run-off result compared to',r'large and weather claims development',r'underlying claims ratio improved'],
                        'Gunstigere vær- og storskader og bedre underliggende skadeprosent motvirkes delvis av svakere avviklingsresultat i bedriftsporteføljen.','temporary')
                    add('cost_explanation','distribution_efficiency',views,'quarter',92,
                        [r'expense ratio rose briefly',r'reduce distribution costs',r'efficient sales channels'],
                        'Kostnadsprosenten steg noe i en nordisk bedriftsportefølje; mer effektive salgskanaler og lavere distribusjonskostnader er tiltak for å bedre denne fremover.')
                    add('event_explanation','workers_comp_provision',views,'ytd',113,
                        [rf'Figures for Q1-Q{q} {y} are impacted by the Supreme Court ruling on Danish workers.{{0,5}} compensation insurance',r'one-off provision of DKK ([\d.,]+)bn pre-tax'],
                        lambda m:'Dansk høyesterettsdom om yrkesskadeforsikring har medført en engangsavsetning på '+fmt(m,1)+' mrd. DKK før skatt. Denne belaster HIÅ-resultatet i bedriftsmarkedet og må skilles fra løpende skadedrift.')
            if has(rf'Interim report Q1-Q{q} {y}') and has(r'Weather claims for the quarter amounted to'):
                add('loss_explanation','workers_comp_adjusted',group('bm'),'ytd',115,
                    [r'one-off',r'provision on Danish workers.{0,6} compensation',r'booked in Q[1-4] '+str(y),r'was ([\d.,]+)% \(([\d.,]+)%\), or ([\d.,]+)% when',r'adjusting for the one-off provision on Danish'],
                    lambda m:'Dansk yrkesskadeavsetning er en viktig forklaring på svekket rapportert CR. Hos Tryg var konsernets skadeprosent '+fmt(m,3)+' % hittil i år, men '+fmt(m,3,3)+' % uten engangsposten, mot '+fmt(m,3,2)+' % året før.','adverse')

                add('loss_explanation','group_weather',group('all'),'quarter',94,
                    [r'DKK ([\d,]+)m \(DKK ([\d,]+)m\), below both',r'benign weather patterns'],
                    lambda m:'Gunstige værforhold reduserte værskadene i en nordisk portefølje fra '+amount(m[0][2])+' til '+amount(m[0][1])+' mill. DKK, og bidro til lavere skadeprosent.' if float(m[0][1].replace(',',''))<float(m[0][2].replace(',','')) else '','weather')
                add('cost_explanation','cost_control',group('all'),'quarter',83,
                    [r'The expense ratio was reported at [\d.,]+%',r'tight cost controls'],
                    'Rapporteringen fremhever stram kostnadskontroll som et konkurransefortrinn; kostnadsandelen må vurderes separat fra endringen i skadeprosenten.')
                add('growth_explanation','group_ytd_price_volume',group('all'),'ytd',95,
                    [r'Insurance revenue growth of [\d.,]+% \([\d.,]+%\)',r'portfolio growth in selected segments',r'profitability initiatives to mitigate inflation'],
                    'Hittil i år har porteføljevekst og prisgrep for å motvirke inflasjon understøttet premieinntektene, særlig i nordisk privatforsikring.','volume')
                add('event_explanation','motor_distribution',group('all'),'quarter',100,
                    [r'Mercedes-Benz.s official insurance partner',r'car brand XPENG was',r'launched on'],
                    'Nye bilforsikringspartnerskap med Mercedes-Benz i Sverige og XPENG i Norge skal styrke salgsveksten fremover. Resultatvirkningen er ikke tallfestet i kvartalet.')
                add('event_explanation','motor_distribution',norway('all'),'quarter',100,
                    [r'In Norway, a partnership with',r'car brand XPENG was',r'launched on'],
                    'Nytt bilforsikringssamarbeid med XPENG i Norge er lansert for å understøtte videre salg. Resultatvirkningen er ikke tallfestet i kvartalet.')
        elif company=='Alm. Brand':
            if has(rf'Q{q} PERFORMANCE') and has(rf'Q1-Q{q} PERFORMANCE') and has(r'Alm\.? Brand Group'):
                add('growth_explanation','bm_soft_market',group('bm'),'ytd',93,
                    [r'increasingly soft market for workers',r'reduce volatility among larger',rf'premium growth of ([\d.,]+)% for Q1-Q{q}'],
                    lambda m:'Svakere yrkesskademarked og selektiv risikoutvelgelse blant store bedriftskunder demper veksten. Uten yrkesskade og industrikunder er rapportert HIÅ-premievekst '+fmt(m,2)+' %.','restraint')
                add('loss_explanation','reinsurance_cost',group('all'),'ytd',92,
                    [r'implemented profitability initiatives and lower reinsurance',r'lower level of property',r'claims in H1'],
                    'Lønnsomhetstiltak, lavere gjenforsikringskostnader og færre eiendomsskader tidligere i året bedrer underliggende skaderesultat.','pricing')
            if has(r'\bPERSONAL LINES\b') and has(r'Personal Lines reported an improved insurance service'):
                add('growth_explanation','bank_distribution',group('pm'),'quarter',96,
                    [r'customer inflow.{0,100}through bank partnerships',r'price adjustments to miti-?\s*gate claims inflation'],
                    'Bankpartnerskap bidrar til kundetilgang og videre vekst i privatporteføljen.','distribution')
                add('loss_explanation','weather_major_claims',group('pm'),'quarter',90,
                    [r'improved underlying claims ratio as well as a',r'lower level of weather-related and major claims'],
                    'Bedre underliggende skadeprosent kombineres med færre vær- og storskader i privatporteføljen.','temporary')
            if has(r'\bCOMMERCIAL LINES\b') and has(r'Commercial Lines reported an insurance service result'):
                add('growth_explanation','bm_soft_market',group('bm'),'quarter',96,
                    [r'continued soft market for',r'volatility for large commercial clients',r'portfolio reported premium growth of ([\d.,]+)%'],
                    lambda m:'Et mykere yrkesskademarked og strengere seleksjon av store kunder trekker ned veksten. Uten yrkesskade og industrikunder var rapportert premievekst '+fmt(m,2)+' %.','restraint')
                add('loss_explanation','runoff_property',group('bm'),'quarter',99,
                    [r'fewer property-related losses',r'higher run-off gains',r'reserve releases in workers.{0,8} compensation'],
                    'Færre eiendomsrelaterte storskader og frigjøring av reserver innen yrkesskade og eiendom forklarer mye av CR-bedringen i en dansk bedriftsportefølje.','temporary')
                add('cost_explanation','lower_revenue_denominator',group('bm'),'quarter',91,
                    [r'Insurance operating expenses totalled DKK ([\d,]+) million',r'against DKK ([\d,]+) million in Q[1-4] '+str(y-1),r'ratio increased slightly to',r'a decrease of\s*-?[\d.,]+% year-on-year'],
                    lambda m:'Kostnadsprosenten steg i en dansk bedriftsportefølje selv om driftskostnadene falt fra '+amount(m[1][1])+' til '+amount(m[0][1])+' mill. DKK, fordi inntektsgrunnlaget ble mindre.' if float(m[0][1].replace(',',''))<float(m[1][1].replace(',','')) else '')
                add('event_explanation','workers_comp_current',group('bm'),'quarter',110,
                    [r'workers.{0,8} compensation ruling',r'negative impact of around ([\d.,]+) percentage points on the',r'underlying claims ratio in the quarter for Commercial Lines'],
                    lambda m:'Dansk yrkesskadedom belaster fortsatt underliggende skadeprosent i en bedriftsportefølje med rundt '+fmt(m,1)+' prosentpoeng i kvartalet, etter at den store engangseffekten ble innregnet tidligere i år.')
    return list({(r['topic'],r['period_type'],tuple(r['views']),r['source_page']):r for r in out}.values())
