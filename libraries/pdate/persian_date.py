from libraries.pdate.abstract_date import AbstractDate
from libraries.pdate.persian.algorithmic_converter import AlgorithmicConverter
from libraries.pdate.persian.lookup_table_converter import LookupTableConverter
from libraries.pdate.util.twelve_months_year import TwelveMonthsYear
from libraries.pdate.year_month_date import YearMonthDate


class PersianDate(AbstractDate, YearMonthDate):

    def __init__(self, year=None, month=None, day_of_month=None, jdn=None, date=None):
        super().__init__(year=year, month=month, day_of_month=day_of_month, jdn=jdn, date=date)

    def to_jdn(self):
        result = LookupTableConverter.to_jdn(self.year, self.month, self.day_of_month)
        return result if result != -1 else AlgorithmicConverter.to_jdn(self.year, self.month, self.day_of_month)

    def from_jdn(self, jdn):
        return LookupTableConverter.from_jdn(jdn) or AlgorithmicConverter.from_jdn(jdn)

    def month_start_of_months_distance(self, months_distance):
        return TwelveMonthsYear.month_start_of_months_distance(self, months_distance, PersianDate)

    def months_distance_to(self, date):
        return TwelveMonthsYear.months_distance_to(self, date)

    @staticmethod
    def month_from_days_count(days):
        return next(i for i, d in enumerate(PersianDate.days_to_month) if d >= days)

    @staticmethod
    def days_in_previous_months(month):
        return PersianDate.days_to_month[month - 1]

    days_to_month = [0, 31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336, 366]
