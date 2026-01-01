from libraries.pdate.abstract_date import AbstractDate
from libraries.pdate.util.twelve_months_year import TwelveMonthsYear


class CivilDate(AbstractDate):
    def __init__(self, year=None, month=None, day_of_month=None, jdn=None, date=None):
        super().__init__(year=year, month=month, day_of_month=day_of_month, jdn=jdn, date=date)

    # Converters
    def to_jdn(self):
        l_year = int(self.year)
        l_month = int(self.month)
        l_day = int(self.day_of_month)
        a = int(-10 / 12)

        if (l_year > 1582) or (l_year == 1582 and l_month > 10) or (l_year == 1582 and l_month == 10 and l_day > 14):
            return (
                (1461 * (l_year + 4800 + (a))) // 4
                + (367 * (l_month - 2 - 12 * (a))) // 12
                - (3 * ((l_year + 4900 + (a)) // 100)) // 4
                + l_day
                - 32075
            )
        else:
            return CivilDate.julian_to_jdn(l_year, l_month, l_day)

    def from_jdn(self, jdn):
        if jdn > 2299160:
            l = jdn + 68569
            n = (4 * l) // 146097
            l -= (146097 * n + 3) // 4
            i = (4000 * (l + 1)) // 1461001
            l = l - (1461 * i) // 4 + 31
            j = (80 * l) // 2447
            day = int(l - (2447 * j) // 80)
            l = j // 11
            month = int(j + 2 - 12 * l)
            year = int(100 * (n - 49) + i + l)
            return [year, month, day]
        else:
            return CivilDate.julian_from_jdn(jdn)

    def month_start_of_months_distance(self, months_distance):
        return TwelveMonthsYear.month_start_of_months_distance(self, months_distance, CivilDate)

    def months_distance_to(self, date):
        return TwelveMonthsYear.months_distance_to(self, date)

    @staticmethod
    def julian_from_jdn(jdn):
        j = jdn + 1402
        k = (j - 1) // 1461
        l = j - 1461 * k
        n = (l - 1) // 365 - l // 1461
        i = l - 365 * n + 30
        j = (80 * i) // 2447
        day = int(i - (2447 * j) // 80)
        i = j // 11
        month = int(j + 2 - 12 * i)
        year = int(4 * k + n + i - 4716)
        return [year, month, day]

    @staticmethod
    def julian_to_jdn(l_year, l_month, l_day):
        return (
            367 * l_year
            - (7 * (l_year + 5001 + (l_month - 9) // 7)) // 4
            + (275 * l_month) // 9
            + l_day
            + 1729777
        )
