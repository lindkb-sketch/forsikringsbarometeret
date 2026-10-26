# Krav til primærkilder for historisk inntektsvekst

Samme beviskrav gjelder for 2024, 2025, 2026 og alle senere rapporteringsår.

## Godkjente kilder

- **Selskapets offisielle kvartalsrapport eller årsrapport**, oppført i selskapets eget rapportarkiv. En rapport kan være lagret hos en distributør/CDN (f.eks. Cision, MFN, Wrepit eller Sanity) **bare dersom selskapet selv lenker til det konkrete dokumentet**.
- Riktig utsteder/juridisk enhet, kvartal, år, valuta, omfang og inntektsdefinisjon skal bekreftes fra selve rapporten og dokumenteres i observasjonen.
- Rapportens fjorårskolonner kan brukes som kilde til 2024-tall når de har en entydig periode og er sammenlignbare med 2025-tallene. Årsrapportens kvartals-/segmentnote kan brukes dersom de samme kravene er oppfylt.
- Presis original-URL, rapportperiode, side/tabell og SHA-256 for nedlastet kilde skal lagres der importøren har tilgang til PDF/fil. Det er ikke tilstrekkelig at nettsiden inneholder en prosent.

## Ikke godkjent

Analytikerestimater, medieoppslag, søketreff, løsrevne regneark, en ikke-verifisert ekstern oppslagsside, manuelt hardkodet vekst eller sammenligning av ulikt selskap, kvartal, HIÅ, valuta eller inntektsbegrep. En URL som *ser* ut som en rapport, må kontrolleres før den tas i bruk.

## Formel

- Q3 2025 mot Q3 2024: `(verifiserte inntekter Q3 2025 / verifiserte inntekter Q3 2024 - 1) * 100`.
- HIÅ Q3 2025 mot HIÅ Q3 2024: samme formel for de **akkumulerte** inntektene, ikke summen av prosentvis kvartalsvekst.
- Fremtidige kvartaler rulleres ved samme periodesammenligning `Y-1 mot Y-2`; ikke gjenbruk Q3 2024 som basis for andre kvartaler.
- For Frende står `Sum driftsinntekter` eksplisitt som særskilt inntektsmål; Storebrand Insurance premiums f.o.a. er en APM og må ikke fremstilles som IFRS-konserninntekter.

## Nåværende gren

`scripts/prior_year_growth_coverage.py` identifiserer manglende kildebevis for **alle sju** og oppdateres etter siste verifiserte kvartal. Den utgir ingen manglende observasjoner som verifiserte.

Fremtind- og Frende-importen utvides for historiske sammenligningskolonner, men ingen ny historisk verdi godkjennes uten bestått parser-/kildekontroll. **Ikke sammenslå** grenen før GitHub-regresjonstester er grønne og de aktuelle gamle kildedokumentene er kontrollert.