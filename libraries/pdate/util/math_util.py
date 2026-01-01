import math

def to_radians(degree: float) -> float:
    """
    Converts degrees to radians.
    
    :param degree: Angle in degrees.
    :return: Angle in radians.
    """
    return degree * math.pi / 180.0

def sin_of_degree(degree: float) -> float:
    """
    Returns the sine of an angle in degrees.
    
    :param degree: Angle in degrees.
    :return: Sine of the angle.
    """
    return math.sin(to_radians(degree))

def cos_of_degree(degree: float) -> float:
    """
    Returns the cosine of an angle in degrees.
    
    :param degree: Angle in degrees.
    :return: Cosine of the angle.
    """
    return math.cos(to_radians(degree))

def tan_of_degree(degree: float) -> float:
    """
    Returns the tangent of an angle in degrees.
    
    :param degree: Angle in degrees.
    :return: Tangent of the angle.
    """
    return math.tan(to_radians(degree))
