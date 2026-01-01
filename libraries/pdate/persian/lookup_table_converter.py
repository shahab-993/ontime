class LookupTableConverter:
    starting_year = 1206
    years_starting_jdn = []

    @staticmethod
    def initialize_years_starting_jdn():
        leap_years = [
            1210, 1214, 1218, 1222, 1226, 1230, 1234, 1238, 1243, 1247, 1251, 1255, 1259, 1263,
            1267, 1271, 1276, 1280, 1284, 1288, 1292, 1296, 1300, 1304, 1309, 1313, 1317, 1321,
            1325, 1329, 1333, 1337, 1342, 1346, 1350, 1354, 1358, 1362, 1366, 1370, 1375, 1379,
            1383, 1387, 1391, 1395, 1399, 1403, 1408, 1412, 1416, 1420, 1424, 1428, 1432, 1436,
            1441, 1445, 1449, 1453, 1457, 1461, 1465, 1469, 1474, 1478, 1482, 1486, 1490, 1494,
            1498
        ]

        LookupTableConverter.years_starting_jdn.append(2388438)  # jdn of 1206
        i = 0
        j = 0
        while i < (1498 - LookupTableConverter.starting_year - 1):
            year = i + LookupTableConverter.starting_year
            next_jdn = LookupTableConverter.years_starting_jdn[i] + (366 if leap_years[j] == year else 365)
            LookupTableConverter.years_starting_jdn.append(next_jdn)
            if year >= leap_years[j] and j + 1 < len(leap_years):
                j += 1
            i += 1

    @staticmethod
    def to_jdn(year: int, month: int, day: int) -> int:
        from libraries.pdate.persian_date import PersianDate
        if year < LookupTableConverter.starting_year or year > LookupTableConverter.starting_year + len(LookupTableConverter.years_starting_jdn) - 1:
            return -1
        return LookupTableConverter.years_starting_jdn[year - LookupTableConverter.starting_year] + PersianDate.days_in_previous_months(month) + day - 1

    @staticmethod
    def from_jdn(jdn: int):
        from libraries.pdate.persian_date import PersianDate
        if jdn < LookupTableConverter.years_starting_jdn[0] or jdn > LookupTableConverter.years_starting_jdn[-1]:
            return None

        year = (jdn - LookupTableConverter.years_starting_jdn[0]) // 366
        while year < len(LookupTableConverter.years_starting_jdn) - 1:
            if jdn < LookupTableConverter.years_starting_jdn[year + 1]:
                break
            year += 1

        start_of_year_jdn = LookupTableConverter.years_starting_jdn[year]
        year += LookupTableConverter.starting_year
        day_of_year = int(jdn - start_of_year_jdn) + 1
        month = PersianDate.month_from_days_count(day_of_year)
        day = day_of_year - PersianDate.days_in_previous_months(month)
        return [year, month, day]

# Initialize the lookup table once
LookupTableConverter.initialize_years_starting_jdn()
