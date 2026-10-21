"""Kontrollerte vekstberegninger for Forsikringsbarometeret. Ingen scraping eller publisering."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

class DataQualityError(ValueError):
    pass

def growth(current, previous, *, scope, currency, metric, source_url):
    if not all([scope, currency, metric, source_url]) or not source_url.startswith(('https://','http://')):
        raise DataQualityError('Kilde, segment, valuta og inntektsbegrep er obligatorisk')
    try:
        a, b = Decimal(str(current)), Decimal(str(previous))
    except (InvalidOperation, TypeError):
        raise DataQualityError('Manglende eller ugyldige inntekter')
    if not a.is_finite() or not b.is_finite() or a < 0 or b <= 0:
        raise DataQualityError('Inntektene må være gyldige; fjorår må være positivt')
    return ((a/b-1)*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

def isolated_quarter(ytd_current, previous_ytd_current, ytd_prior, previous_ytd_prior):
    try:
        a=Decimal(str(ytd_current))-Decimal(str(previous_ytd_current))
        b=Decimal(str(ytd_prior))-Decimal(str(previous_ytd_prior))
    except (InvalidOperation, TypeError):
        raise DataQualityError('Manglende Hiå-grunnlag')
    if not a.is_finite() or not b.is_finite() or a < 0 or b <= 0:
        raise DataQualityError('Ugyldig isolert kvartal eller fjorårsgrunnlag')
    return a,b

def validate_row(row):
    required=('company','period','scope','currency','metric','source_url','current','previous')
    if any(k not in row for k in required):
        raise DataQualityError('Mangler obligatorisk felt')
    value=growth(row['current'],row['previous'],scope=row['scope'],currency=row['currency'],metric=row['metric'],source_url=row['source_url'])
    if 'reported_growth' in row and abs(value-Decimal(str(row['reported_growth']))) > Decimal('0.2'):
        raise DataQualityError('Rapportert vekst avviker fra beregnet vekst')
    return value
