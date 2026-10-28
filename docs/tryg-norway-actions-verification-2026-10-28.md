# Tryg Norge: kontroll av PDF-import

GitHub Actions `.github/workflows/update.yml` har `push` på `main` og kjører `scripts/run_pipeline.py` før validering og publisering.

Kontrollpunkter:
- PDF-rapporten må identifisere «Norwegian general insurance» og korrekt kvartal/år.
- Norge-tall må ikke erstattes med konserntall.
- CR skal stemme med skadeprosent + kostnadsprosent.
- Importen skal avstemme historiske Norge-tall mot allerede godkjente observasjoner.
- Excel brukes bare som reservekilde dersom PDF ikke kan valideres.
- Nettstedets feed og GitHub Pages må bekreftes i Actions-loggen; en commit alene beviser ikke vellykket publisering.
