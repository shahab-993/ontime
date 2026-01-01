import math

from libraries.pdate.civil_date import CivilDate
from libraries.pdate.util.math_util import sin_of_degree, to_radians


class FallbackIslamicConverter:
    NMONTHS = (1405 * 12) + 1

    @staticmethod
    def floor(d: float) -> int:
        return math.floor(d)

    @staticmethod
    def to_jdn(year: int, month: int, day: int) -> int:
        if year < 0:
            year += 1
        k = (month + year * 12 - FallbackIslamicConverter.NMONTHS)
        return FallbackIslamicConverter.floor(FallbackIslamicConverter.visibility(k + 1048) + day + 0.5)

    @staticmethod
    def tmoonphase(n: int, nph: int) -> float:
        k = n + nph / 4.0
        T = k / 1236.85
        t2 = T * T
        t3 = t2 * T
        jd = (
            2415020.75933 + 29.53058868 * k - 0.0001178 * t2 - 0.000000155 * t3
            + 0.00033 * sin_of_degree(166.56 + 132.87 * T - 0.009173 * t2)
        )

        # Sun's mean anomaly
        sa = to_radians(359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3)

        # Moon's mean anomaly
        ma = to_radians(306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3)

        # Moon's argument of latitude
        tf = to_radians(2 * (21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3))

        xtra = 0.0
        if nph == 0 or nph == 2:
            xtra = (
                (0.1734 - 0.000393 * T) * math.sin(sa)
                + 0.0021 * math.sin(2 * sa)
                - 0.4068 * math.sin(ma)
                + 0.0161 * math.sin(2 * ma)
                - 0.0004 * math.sin(3 * ma)
                + 0.0104 * math.sin(tf)
                - 0.0051 * math.sin(sa + ma)
                - 0.0074 * math.sin(sa - ma)
                + 0.0004 * math.sin(tf + sa)
                - 0.0004 * math.sin(tf - sa)
                - 0.0006 * math.sin(tf + ma)
                + 0.001 * math.sin(tf - ma)
                + 0.0005 * math.sin(sa + 2 * ma)
            )
        elif nph == 1 or nph == 3:
            xtra = (
                (0.1721 - 0.0004 * T) * math.sin(sa)
                + 0.0021 * math.sin(2 * sa)
                - 0.628 * math.sin(ma)
                + 0.0089 * math.sin(2 * ma)
                - 0.0004 * math.sin(3 * ma)
                + 0.0079 * math.sin(tf)
                - 0.0119 * math.sin(sa + ma)
                - 0.0047 * math.sin(sa - ma)
                + 0.0003 * math.sin(tf + sa)
                - 0.0004 * math.sin(tf - sa)
                - 0.0006 * math.sin(tf + ma)
                + 0.0021 * math.sin(tf - ma)
                + 0.0003 * math.sin(sa + 2 * ma)
                + 0.0004 * math.sin(sa - 2 * ma)
                - 0.0003 * math.sin(2 * sa + ma)
            )
            if nph == 1:
                xtra += 0.0028 - 0.0004 * math.cos(sa) + 0.0003 * math.cos(ma)
            else:
                xtra += -0.0028 + 0.0004 * math.cos(sa) - 0.0003 * math.cos(ma)

        # Convert from Ephemeris Time (ET) to (approximate) Universal Time (UT)
        return jd + xtra - (0.41 + 1.2053 * T + 0.4992 * t2) / 1440

    @staticmethod
    def visibility(n: int) -> float:
        TIMZ = 3.0
        MINAGE = 13.5
        SUNSET = 19.5
        TIMDIF = SUNSET - MINAGE
        jd = FallbackIslamicConverter.tmoonphase(n, 0)
        d = FallbackIslamicConverter.floor(jd)
        tf = jd - d
        if tf <= 0.5:
            return jd + 1.0
        else:
            tf = (tf - 0.5) * 24 + TIMZ
            return jd + 1.0 if tf > TIMDIF else jd

    @staticmethod
    def from_jdn(jd: int) -> list:
        civil = CivilDate(None, None, None,jd)
        year = civil.year
        month = civil.month
        day = civil.day_of_month
        k = FallbackIslamicConverter.floor(
            0.6 + (year + (month if month % 2 == 0 else month - 1) / 12.0 + day / 365.0 - 1900) * 12.3685
        )
        while True:
            mjd = FallbackIslamicConverter.visibility(k)
            if mjd <= jd - 0.5:
                break
            k -= 1
        k += 1
        hm = k - 1048
        year = 1405 + hm // 12
        month = int(hm % 12) + 1
        if hm != 0 and month <= 0:
            month += 12
            year -= 1
        if year <= 0:
            year -= 1
        day = FallbackIslamicConverter.floor(jd - mjd + 0.5)
        return [year, month, day]
