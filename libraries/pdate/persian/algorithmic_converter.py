import math

from libraries.pdate.civil_date import CivilDate
from libraries.pdate.util.math_util import sin_of_degree, cos_of_degree, tan_of_degree


class AlgorithmicConverter:
    project_jdn_offset = 1721426  # Offset from Jdn to jdn used in this converter
    persian_epoch = 226895  # Equivalent to new DateTime(622, 3, 22).Ticks / TicksPerDay
    mean_tropical_year_in_days = 365.242189
    full_circle_of_arc = 360.0
    mean_speed_of_sun = mean_tropical_year_in_days / full_circle_of_arc
    half_circle_of_arc = 180
    two_degrees_after_spring = 2.0
    noon_2000_jan_01 = 730120.5
    days_in_uniform_length_century = 36525
    start_of_1810 = CivilDate(1810, 1, 1).to_jdn() - project_jdn_offset
    start_of_1900_century = CivilDate(1900, 1, 1).to_jdn() - project_jdn_offset
    twelve_hours = 0.5  # Half a day
    seconds_per_day = 24 * 60 * 60
    seconds_per_minute = 60
    minutes_per_degree = 60

    coefficients_1900_to_1987 = [
        -0.00002,
        0.000297,
        0.025184,
        -0.181133,
        0.553040,
        -0.861938,
        0.677066,
        -0.212591,
    ]

    coefficients_1800_to_1899 = [
        -0.000009,
        0.003844,
        0.083563,
        0.865736,
        4.867575,
        15.845535,
        31.332267,
        38.291999,
        28.316289,
        11.636204,
        2.043794,
    ]

    coefficients_1700_to_1799 = [
        8.118780842,
        -0.005092142,
        0.003336121,
        -0.0000266484,
    ]

    coefficients_1620_to_1699 = [
        196.58333,
        -4.0675,
        0.0219167,
    ]

    lambda_coefficients = [
        280.46645,
        36000.76983,
        0.0003032,
    ]

    anomaly_coefficients = [
        357.52910,
        35999.05030,
        -0.0001559,
        -0.00000048,
    ]

    eccentricity_coefficients = [
        0.016708617,
        -0.000042037,
        -0.0000001236,
    ]

    coefficients = [
        (23 + 26 / 60 + 21.448 / 3600),
        (0, 0, -46.8150 / 3600),
        (0, 0, -0.00059 / 3600),
        (0, 0, 0.001813 / 3600),
    ]

    coefficients_a = [
        124.90,
        -1934.134,
        0.002063,
    ]

    coefficients_b = [
        201.11,
        72001.5377,
        0.00057,
    ]

    longitude_spring = 0.0

    @staticmethod
    def to_jdn(year, month, day):
        from libraries.pdate.persian_date import PersianDate
        approximate_half_year = 180
        ordinal_day = PersianDate.days_in_previous_months(month) + day - 1
        approximate_days_from_epoch_for_year_start = int(AlgorithmicConverter.mean_tropical_year_in_days * (year - 1))
        year_start = AlgorithmicConverter.persian_new_year_on_or_before(
            AlgorithmicConverter.persian_epoch + approximate_days_from_epoch_for_year_start + approximate_half_year
        )
        year_start += ordinal_day
        return year_start + AlgorithmicConverter.project_jdn_offset

    @staticmethod
    def from_jdn(jdn):
        from libraries.pdate.persian_date import PersianDate
        jdn += 1
        year_start = AlgorithmicConverter.persian_new_year_on_or_before(jdn - AlgorithmicConverter.project_jdn_offset)
        y = int(math.floor((year_start - AlgorithmicConverter.persian_epoch) / AlgorithmicConverter.mean_tropical_year_in_days + 0.5)) + 1
        ordinal_day = int(jdn - AlgorithmicConverter.to_jdn(y, 1, 1))
        m = PersianDate.month_from_days_count(ordinal_day)
        d = ordinal_day - PersianDate.days_in_previous_months(m)
        return [y, m, d]

    @staticmethod
    def as_season(longitude):
        return longitude + AlgorithmicConverter.full_circle_of_arc if longitude < 0 else longitude

    @staticmethod
    def init_longitude(longitude):
        return AlgorithmicConverter.normalize_longitude(longitude + AlgorithmicConverter.half_circle_of_arc) - AlgorithmicConverter.half_circle_of_arc

    @staticmethod
    def normalize_longitude(longitude):
        longitude %= AlgorithmicConverter.full_circle_of_arc
        if longitude < 0:
            longitude += AlgorithmicConverter.full_circle_of_arc
        return longitude

    @staticmethod
    def estimate_prior(longitude, time):
        time_sun_last_at_longitude = time - AlgorithmicConverter.mean_speed_of_sun * AlgorithmicConverter.as_season(
            AlgorithmicConverter.init_longitude(AlgorithmicConverter.compute(time) - longitude)
        )
        longitude_error_delta = AlgorithmicConverter.init_longitude(AlgorithmicConverter.compute(time_sun_last_at_longitude) - longitude)
        return min(time, time_sun_last_at_longitude - AlgorithmicConverter.mean_speed_of_sun * longitude_error_delta)

    @staticmethod
    def compute(time):
        julian_centuries = AlgorithmicConverter.julian_centuries(time)
        lambda_value = 282.7771834 + (36000.76953744 * julian_centuries) + (
            0.000005729577951308232 * AlgorithmicConverter.sum_long_sequence_of_periodic_terms(julian_centuries)
        )
        longitude = lambda_value + AlgorithmicConverter.aberration(julian_centuries) + AlgorithmicConverter.nutation(julian_centuries)
        return AlgorithmicConverter.init_longitude(longitude)

    @staticmethod
    def polynomial_sum(coefficients, indeterminate):
        sum_value = coefficients[0]
        indeterminate_raised = 1.0
        for i in range(1, len(coefficients)):
            indeterminate_raised *= indeterminate
            sum_value += coefficients[i] * indeterminate_raised
        return sum_value

    @staticmethod
    def nutation(julian_centuries):
        a = AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_a, julian_centuries)
        b = AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_b, julian_centuries)
        return -0.004778 * sin_of_degree(a) - 0.0003667 * sin_of_degree(b)

    @staticmethod
    def aberration(julian_centuries):
        return (0.0000974 * cos_of_degree(177.63 + 35999.01848 * julian_centuries)) - 0.005575

    terms = [
        (403406, 270.54861, 0.9287892),
        (195207, 340.19128, 35999.1376958),
        (119433, 63.91854, 35999.4089666),
        (112392, 331.2622, 35998.7287385),
        (3891, 317.843, 71998.20261),
        (2819, 86.631, 71998.4403),
        (1721, 240.052, 36000.35726),
        (660, 310.26, 71997.4812),
        (350, 247.23, 32964.4678),
        (334, 260.87, -19.441),
        (314, 297.82, 445267.1117),
        (268, 343.14, 45036.884),
        (242, 166.79, 3.1008),
        (234, 81.53, 22518.4434),
        (158, 3.5, -19.9739),
        (132, 132.75, 65928.9345),
        (129, 182.95, 9038.0293),
        (114, 162.03, 3034.7684),
        (99, 29.8, 33718.148),
        (93, 266.4, 3034.448),
        (86, 249.2, -2280.773),
        (78, 157.6, 29929.992),
        (72, 257.8, 31556.493),
        (68, 185.1, 149.588),
        (64, 69.9, 9037.75),
        (46, 8.0, 107997.405),
        (38, 197.1, -4444.176),
        (37, 250.4, 151.771),
        (32, 65.3, 67555.316),
        (29, 162.7, 31556.08),
        (28, 341.5, -4561.54),
        (27, 291.6, 107996.706),
        (27, 98.5, 1221.655),
        (25, 146.7, 62894.167),
        (24, 110.0, 31437.369),
        (21, 5.2, 14578.298),
        (21, 342.6, -31931.757),
        (20, 230.9, 34777.243),
        (18, 256.1, 1221.999),
        (17, 45.3, 62894.511),
        (14, 242.9, -4442.039),
        (13, 115.2, 107997.909),
        (13, 151.8, 119.066),
        (13, 285.3, 16859.071),
        (12, 53.3, -4.578),
        (10, 126.6, 26895.292),
        (10, 205.7, -39.127),
        (10, 85.9, 12297.536),
        (10, 146.1, 90073.778),
    ]

    @staticmethod
    def sum_long_sequence_of_periodic_terms(julian_centuries):
        return sum(x * sin_of_degree(y + z * julian_centuries) for x, y, z in AlgorithmicConverter.terms)

    @staticmethod
    def julian_centuries(moment):
        dynamical_moment = moment + AlgorithmicConverter.ephemeris_correction(moment)
        return (dynamical_moment - AlgorithmicConverter.noon_2000_jan_01) / AlgorithmicConverter.days_in_uniform_length_century

    @staticmethod
    def centuries_from_1900(gregorian_year):
        july_1st_of_year = CivilDate(gregorian_year, 7, 1).to_jdn() - AlgorithmicConverter.project_jdn_offset
        return (july_1st_of_year - AlgorithmicConverter.start_of_1900_century) / AlgorithmicConverter.days_in_uniform_length_century

    @staticmethod
    def angle(degrees, minutes, seconds):
        return (seconds / AlgorithmicConverter.seconds_per_minute + minutes) / AlgorithmicConverter.minutes_per_degree + degrees

    @staticmethod
    def get_gregorian_year(number_of_days):
        return CivilDate(math.floor(number_of_days) + AlgorithmicConverter.project_jdn_offset).year

    @staticmethod
    def ephemeris_correction(time):
        year = AlgorithmicConverter.get_gregorian_year(time)
        for algorithm in AlgorithmicConverter.CorrectionAlgorithm:
            if algorithm.lowest_year <= year:
                return algorithm.ephemeris_correction(year)
        return AlgorithmicConverter.CorrectionAlgorithm.Default.ephemeris_correction(year)

    @staticmethod
    def as_day_fraction(longitude):
        return longitude / AlgorithmicConverter.full_circle_of_arc

    @staticmethod
    def obliquity(julian_centuries):
        return AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients, julian_centuries)

    @staticmethod
    def equation_of_time(time):
        julian_centuries = AlgorithmicConverter.julian_centuries(time)
        lambda_value = AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.lambda_coefficients, julian_centuries)
        anomaly = AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.anomaly_coefficients, julian_centuries)
        eccentricity = AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.eccentricity_coefficients, julian_centuries)
        epsilon = AlgorithmicConverter.obliquity(julian_centuries)
        tan_half_epsilon = tan_of_degree(epsilon / 2)
        y = tan_half_epsilon * tan_half_epsilon
        dividend = (
            y * sin_of_degree(2 * lambda_value)
            - 2 * eccentricity * sin_of_degree(anomaly)
            + 4 * eccentricity * y * sin_of_degree(anomaly) * cos_of_degree(2 * lambda_value)
            - 0.5 * y**2 * sin_of_degree(4 * lambda_value)
            - 1.25 * eccentricity**2 * sin_of_degree(2 * anomaly)
        )
        divisor = 2 * math.pi
        equation = dividend / divisor
        return min(abs(equation), equation) if abs(equation) <= AlgorithmicConverter.twelve_hours else AlgorithmicConverter.twelve_hours

    @staticmethod
    def as_local_time(apparent_midday, longitude):
        universal_time = apparent_midday - AlgorithmicConverter.as_day_fraction(longitude)
        return apparent_midday - AlgorithmicConverter.equation_of_time(universal_time)

    @staticmethod
    def midday(date, longitude):
        return AlgorithmicConverter.as_local_time(date + AlgorithmicConverter.twelve_hours, longitude) - AlgorithmicConverter.as_day_fraction(longitude)

    @staticmethod
    def midday_at_persian_observation_site(date):
        return AlgorithmicConverter.midday(date, AlgorithmicConverter.init_longitude(52.5))

    @staticmethod
    def persian_new_year_on_or_before(number_of_days):
        date = number_of_days
        approx = AlgorithmicConverter.estimate_prior(AlgorithmicConverter.longitude_spring, AlgorithmicConverter.midday_at_persian_observation_site(date))
        lower_bound_new_year_day = math.floor(approx) - 1
        upper_bound_new_year_day = lower_bound_new_year_day + 3
        day = lower_bound_new_year_day
        while day != upper_bound_new_year_day:
            midday = AlgorithmicConverter.midday_at_persian_observation_site(day)
            l = AlgorithmicConverter.compute(midday)
            if AlgorithmicConverter.longitude_spring <= l <= AlgorithmicConverter.two_degrees_after_spring:
                break
            day += 1
        return day - 1

    class CorrectionAlgorithm:
        def __init__(self, lowest_year, ephemeris_correction):
            self.lowest_year = lowest_year
            self.ephemeris_correction = ephemeris_correction

        @staticmethod
        def ephemeris_default(year):
            january_1st_of_year = CivilDate(year, 1, 1).to_jdn() - AlgorithmicConverter.project_jdn_offset
            days_since_start_of_1810 = (january_1st_of_year - AlgorithmicConverter.start_of_1810)
            x = AlgorithmicConverter.twelve_hours + days_since_start_of_1810
            return (x**2 / 41048480 - 15) / AlgorithmicConverter.seconds_per_day

        @staticmethod
        def ephemeris_1988_to_2019(year):
            return (year - 1933.0) / AlgorithmicConverter.seconds_per_day

        @staticmethod
        def ephemeris_1900_to_1987(year):
            return AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_1900_to_1987, AlgorithmicConverter.centuries_from_1900(year))

        @staticmethod
        def ephemeris_1800_to_1899(year):
            return AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_1800_to_1899, AlgorithmicConverter.centuries_from_1900(year))

        @staticmethod
        def ephemeris_1700_to_1799(year):
            return AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_1700_to_1799, year - 1700.0) / AlgorithmicConverter.seconds_per_day

        @staticmethod
        def ephemeris_1620_to_1699(year):
            return AlgorithmicConverter.polynomial_sum(AlgorithmicConverter.coefficients_1620_to_1699, year - 1600.0) / AlgorithmicConverter.seconds_per_day

    CorrectionAlgorithm.Default = CorrectionAlgorithm(2020, CorrectionAlgorithm.ephemeris_default)
    CorrectionAlgorithm.Year1988to2019 = CorrectionAlgorithm(1988, CorrectionAlgorithm.ephemeris_1988_to_2019)
    CorrectionAlgorithm.Year1900to1987 = CorrectionAlgorithm(1900, CorrectionAlgorithm.ephemeris_1900_to_1987)
    CorrectionAlgorithm.Year1800to1899 = CorrectionAlgorithm(1800, CorrectionAlgorithm.ephemeris_1800_to_1899)
    CorrectionAlgorithm.Year1700to1799 = CorrectionAlgorithm(1700, CorrectionAlgorithm.ephemeris_1700_to_1799)
    CorrectionAlgorithm.Year1620to1699 = CorrectionAlgorithm(1620, CorrectionAlgorithm.ephemeris_1620_to_1699)
