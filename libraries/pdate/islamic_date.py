from libraries.pdate.abstract_date import AbstractDate
from libraries.pdate.islamic.fallback_islamic_converter import FallbackIslamicConverter
from libraries.pdate.islamic.iranian_islamic_date_converter import IranianIslamicDateConverter
from libraries.pdate.islamic.umm_al_qura_converter import UmmAlQuraConverter
from libraries.pdate.util.twelve_months_year import TwelveMonthsYear
from libraries.pdate.year_month_date import YearMonthDate


class IslamicDate(AbstractDate, YearMonthDate):

    def __init__(self, year=None, month=None, day_of_month=None, jdn=None, date=None):
        super().__init__(year=year, month=month, day_of_month=day_of_month, jdn=jdn, date=date)

    def to_jdn(self):
        year = self.year
        month = self.month
        day = self.day_of_month

        table_result = (UmmAlQuraConverter.to_jdn(year, month, day) if IslamicDate.use_umm_al_qura
                        else IranianIslamicDateConverter.to_jdn(year, month, day))

        if table_result != -1:
            return table_result - IslamicDate.islamic_offset
        else:
            return FallbackIslamicConverter.to_jdn(year, month, day) - IslamicDate.islamic_offset

    def from_jdn(self, jdn):
        jdn += IslamicDate.islamic_offset
        result = (UmmAlQuraConverter.from_jdn(jdn) if IslamicDate.use_umm_al_qura
                  else IranianIslamicDateConverter.from_jdn(jdn))
        
        return result or FallbackIslamicConverter.from_jdn(jdn)

    def month_start_of_months_distance(self, months_distance):
        return TwelveMonthsYear.month_start_of_months_distance(self, months_distance, IslamicDate)

    def months_distance_to(self, date):
        return TwelveMonthsYear.months_distance_to(self, date)

    # Converters
    use_umm_al_qura = False
    islamic_offset = 0
