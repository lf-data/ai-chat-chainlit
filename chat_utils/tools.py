from langchain.tools import tool
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
from typing import Annotated, Optional
import re
import requests
from bs4 import BeautifulSoup
from langchain_tavily import TavilySearch
import os
import math
from math import sqrt, floor, ceil, exp, log, sin, cos, tan, pi
from math import factorial as math_factorial, comb, erf
import random
from chat_utils.openai_provider import math_model
from langchain.agents import create_agent
from chat_utils.prompts import SYSTEM_PROMPT_MATH

@tool()
async def current_time() -> str:
    """
    Get the current date and time in the Europe/Rome timezone.
    """
    now = datetime.now(ZoneInfo("Europe/Rome"))
    return json.dumps(
        {"time": now.strftime("%Y-%m-%d %H:%M:%S"), "timezone": "Europe/Rome"}
    )


@tool()
async def add_days(
    date_str: Annotated[str, "Date string in YYYY-MM-DD format"],
    days: Annotated[int, "Number of days to add"],
) -> str:
    """
    Add a number of days to a given date string (YYYY-MM-DD) and return the new date as a string.
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = date + timedelta(days=days)
    return new_date.strftime("%Y-%m-%d")


@tool()
async def days_between(
    date_str1: Annotated[str, "First date string in YYYY-MM-DD format"],
    date_str2: Annotated[str, "Second date string in YYYY-MM-DD format"],
) -> int:
    """
    Calculate the number of days between two date strings (YYYY-MM-DD).
    """
    date1 = datetime.strptime(date_str1, "%Y-%m-%d")
    date2 = datetime.strptime(date_str2, "%Y-%m-%d")
    return abs((date2 - date1).days)


@tool()
async def convert_timezone(
    datetime_str: Annotated[str, "Date in ISO 8601 format, e.g. 2025-03-01T15:30:00"],
    from_tz: Annotated[str, "Timezone to convert from, e.g. Europe/Rome"],
    to_tz: Annotated[str, "Timezone to convert to es. America/New_York"],
) -> str:
    """
    Convert a date/time from one timezone to another and return an ISO 8601 string with offset.
    """
    # Se datetime_str è senza timezone, viene interpretato nel fuso from_tz
    dt = datetime.fromisoformat(datetime_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(from_tz))
    else:
        # Se ha già tzinfo, lo si converte prima a from_tz per coerenza
        dt = dt.astimezone(ZoneInfo(from_tz))

    dt_converted = dt.astimezone(ZoneInfo(to_tz))
    return dt_converted.isoformat()


@tool()
async def next_weekday(
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    weekday: Annotated[int, "Day of the week (0=Monday ... 6=Sunday)"],
) -> str:
    """
    Return the next date (EXCLUDING the start date) that falls on the specified weekday.
    """
    date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    days_ahead = (weekday - date_obj.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_date = date_obj + timedelta(days=days_ahead)
    return next_date.isoformat()


@tool()
async def text_cleaner(
    raw_text: Annotated[str, "Input text to be cleaned"],
    remove_html: Annotated[bool, "If True, remove HTTML tags"] = True,
    normalize_spaces: Annotated[bool, "If True, normalize \\n"] = True,
) -> str:
    """Cleans text from basic HTML and normalizes spaces."""
    text = raw_text

    if remove_html:
        # Rimozione molto semplice dei tag HTML
        text = re.sub(r"<[^>]+>", " ", text)

    if normalize_spaces:
        text = re.sub(r"\s+", " ", text).strip()

    return text


@tool()
async def fetch_url(
    url: Annotated[str, "URL of page to fetch"],
    timeout_sec: Annotated[int, "Timeout in seconds"] = 10,
) -> dict:
    """
    Download the content of a web page and return title, status, and main text (paragraphs).
    In case of HTTP error, returns a dictionary with the 'error' key.
    """
    try:
        resp = requests.get(url, timeout=timeout_sec)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {
            "url": url,
            "error": str(e),
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    main_text = "\n\n".join(p for p in paragraphs if p)

    return {
        "url": url,
        "status_code": resp.status_code,
        "title": title,
        "text": main_text or resp.text,
    }


@tool()
async def get_website_metadata(
    url: Annotated[str, "URL of website to extract metadata from"],
    timeout_sec: Annotated[int, "Timeout for HTTP request"] = 10,
) -> dict:
    """
    Extract basic metadata (title, description, keywords, favicon) from a web page.
    """
    try:
        resp = requests.get(url, timeout=timeout_sec)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {
            "url": url,
            "error": str(e),
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description_tag = soup.find("meta", attrs={"name": "description"})
    keywords_tag = soup.find("meta", attrs={"name": "keywords"})
    icon_tag = soup.find("link", rel=lambda v: v and "icon" in v.lower())

    return {
        "url": url,
        "title": title,
        "meta_description": (
            description_tag.get("content", "").strip()
            if description_tag and description_tag.get("content")
            else None
        ),
        "meta_keywords": (
            keywords_tag.get("content", "").strip()
            if keywords_tag and keywords_tag.get("content")
            else None
        ),
        "favicon": icon_tag.get("href") if icon_tag and icon_tag.get("href") else None,
    }

@tool()
async def add(numbers: Annotated[list[float], "List of input numbers"]) -> float:
    """
    Sum a list of numbers.
    """
    return float(sum(numbers))


@tool()
async def subtract(
    a: Annotated[float, "Minuend"], b: Annotated[float, "Subtrahend"]
) -> float:
    """
    Subtract b from a (a - b).
    """
    return float(a - b)


@tool()
async def multiply(numbers: Annotated[list[float], "List of input numbers"]) -> float:
    """
    Multiply a list of numbers.
    """
    result = 1.0
    for n in numbers:
        result *= n
    return float(result)


@tool()
async def divide(
    a: Annotated[float, "Dividend"], b: Annotated[float, "Divisor"]
) -> float:
    """
    Divide a by b (a / b).
    """
    if b == 0:
        raise ValueError("Division by zero")
    return float(a / b)


@tool()
async def abs_value(
    x: Annotated[float, "The number for which to compute the absolute value"],
) -> float:
    """Compute the absolute value of a number."""
    return abs(x)


@tool()
async def sqrt_value(
    x: Annotated[
        float, "The number for which to compute the square root (must be >= 0)"
    ],
) -> float:
    """Compute the square root of a non-negative number."""
    if x < 0:
        raise ValueError("sqrt_value: x must be non-negative.")
    return sqrt(x)


@tool()
async def nth_root(
    x: Annotated[float, "The number for which to compute the n-th root"],
    n: Annotated[int, "The degree of the root (must be a non-zero integer)"],
) -> float:
    """
    Compute the n-th root of a number.

    Note: for even n, x must be non-negative in the real domain.
    """
    if n == 0:
        raise ValueError("nth_root: n must be non-zero.")
    if x < 0 and n % 2 == 0:
        raise ValueError("nth_root: for even n, x must be non-negative.")
    return x ** (1.0 / n)


@tool()
async def mod(
    a: Annotated[float, "The dividend in the modulo operation"],
    b: Annotated[float, "The divisor in the modulo operation (must be non-zero)"],
) -> float:
    """Compute the remainder of the division a % b."""
    if b == 0:
        raise ValueError("mod: divisor b must be non-zero.")
    return a % b


@tool()
async def floor_value(
    x: Annotated[float, "The number to be rounded down to the nearest integer"],
) -> int:
    """Return the floor of x as an integer."""
    return floor(x)


@tool()
async def ceil_value(
    x: Annotated[float, "The number to be rounded up to the nearest integer"],
) -> int:
    """Return the ceiling of x as an integer."""
    return ceil(x)


@tool()
async def round_value(
    x: Annotated[float, "The number to be rounded"],
    ndigits: Annotated[
        int, "Number of decimal places to round to; can be negative"
    ] = 0,
) -> float:
    """Round a number to a given precision in decimal digits."""
    return round(x, ndigits)


@tool()
async def min_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numbers from which to compute the minimum value",
    ],
) -> float:
    """Return the minimum value in a non-empty list of numbers."""
    if not numbers:
        raise ValueError("min_value: numbers list must not be empty.")
    return min(numbers)


@tool()
async def max_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numbers from which to compute the maximum value",
    ],
) -> float:
    """Return the maximum value in a non-empty list of numbers."""
    if not numbers:
        raise ValueError("max_value: numbers list must not be empty.")
    return max(numbers)


@tool()
async def exp_value(
    x: Annotated[float, "The exponent used in the natural exponential function e**x"],
) -> float:
    """Compute the natural exponential of x (e**x)."""
    return exp(x)


@tool()
async def ln_value(
    x: Annotated[
        float, "The positive number for which to compute the natural logarithm"
    ],
) -> float:
    """Compute the natural logarithm (base e) of a positive number."""
    if x <= 0:
        raise ValueError("ln_value: x must be strictly positive.")
    return log(x)


@tool()
async def log_value(
    x: Annotated[float, "The positive number for which to compute the logarithm"],
    base: Annotated[
        float,
        "The base of the logarithm; must be positive and not equal to 1",
    ] = 10.0,
) -> float:
    """Compute the logarithm of x with a given base (default is base 10)."""
    if x <= 0:
        raise ValueError("log_value: x must be strictly positive.")
    if base <= 0 or base == 1.0:
        raise ValueError("log_value: base must be positive and not equal to 1.")
    return log(x, base)


@tool()
async def sin_value(
    angle: Annotated[float, "The angle in radians for which to compute the sine"],
) -> float:
    """Compute the sine of an angle given in radians."""
    return sin(angle)


@tool()
async def cos_value(
    angle: Annotated[float, "The angle in radians for which to compute the cosine"],
) -> float:
    """Compute the cosine of an angle given in radians."""
    return cos(angle)


@tool()
async def tan_value(
    angle: Annotated[float, "The angle in radians for which to compute the tangent"],
) -> float:
    """Compute the tangent of an angle given in radians."""
    return tan(angle)


@tool()
async def deg_to_rad(
    degrees: Annotated[float, "The angle in degrees to be converted to radians"],
) -> float:
    """Convert an angle from degrees to radians."""
    return degrees * pi / 180.0


@tool()
async def rad_to_deg(
    radians: Annotated[float, "The angle in radians to be converted to degrees"],
) -> float:
    """Convert an angle from radians to degrees."""
    return radians * 180.0 / pi


@tool()
async def mean_value(numbers: Annotated[list[float], "List of input numbers"]) -> float:
    """
    Compute the arithmetic mean of a list of numbers.
    """
    if len(numbers) == 0:
        raise ValueError("Cannot compute mean of empty list")
    return float(sum(numbers) / len(numbers))


@tool()
async def stddev_value(
    numbers: Annotated[list[float], "List of input numbers"],
) -> float:
    """
    Compute the population standard deviation of a list of numbers.
    """
    if len(numbers) == 0:
        raise ValueError("Cannot compute stddev of empty list")

    m = sum(numbers) / len(numbers)
    var = sum((x - m) ** 2 for x in numbers) / len(numbers)
    return float(math.sqrt(var))


@tool()
async def power(a: Annotated[float, "Base"], b: Annotated[float, "Exponent"]) -> float:
    """
    Compute a raised to the power of b (a^b).
    """
    return float(a**b)


@tool()
async def factorial_value(
    n: Annotated[int, "A non-negative integer for which to compute the factorial"],
) -> int:
    """Compute the factorial of a non-negative integer n (n!)."""
    if n < 0:
        raise ValueError("factorial_value: n must be non-negative.")
    return math_factorial(n)


@tool()
async def binomial_coefficient(
    n: Annotated[int, "The total number of items (must be non-negative)"],
    k: Annotated[int, "The number of items to choose (0 <= k <= n)"],
) -> int:
    """Compute the binomial coefficient 'n choose k'."""
    if n < 0:
        raise ValueError("binomial_coefficient: n must be non-negative.")
    if k < 0 or k > n:
        raise ValueError("binomial_coefficient: k must satisfy 0 <= k <= n.")
    return comb(n, k)


@tool()
async def dot_product(
    v1: Annotated[list[float], "First vector of real numbers"],
    v2: Annotated[list[float], "Second vector of real numbers (same length as v1)"],
) -> float:
    """Compute the dot product of two vectors of the same length."""
    if len(v1) != len(v2):
        raise ValueError("dot_product: vectors must have the same length.")
    if not v1:
        raise ValueError("dot_product: vectors must not be empty.")
    return float(sum(a * b for a, b in zip(v1, v2)))


@tool()
async def matrix_vector_multiply(
    matrix: Annotated[
        list[list[float]],
        "Matrix represented as a list of rows; all rows must have the same length",
    ],
    vector: Annotated[
        list[float],
        "Vector of real numbers; its length must equal the number of columns in the matrix",
    ],
) -> list[float]:
    """Multiply a matrix by a vector (matrix * vector)."""
    if not matrix or not matrix[0]:
        raise ValueError("matrix_vector_multiply: matrix must not be empty.")
    num_cols = len(matrix[0])
    if len(vector) != num_cols:
        raise ValueError(
            "matrix_vector_multiply: vector length must equal the number of columns in the matrix."
        )
    for row in matrix:
        if len(row) != num_cols:
            raise ValueError(
                "matrix_vector_multiply: matrix rows must all have the same length."
            )

    result = [sum(row[j] * vector[j] for j in range(num_cols)) for row in matrix]
    return result


@tool()
async def matrix_multiply(
    a: Annotated[
        list[list[float]],
        "Left matrix A as a list of rows; all rows must have the same length",
    ],
    b: Annotated[
        list[list[float]],
        "Right matrix B as a list of rows; all rows must have the same length",
    ],
) -> list[list[float]]:
    """Multiply two matrices A and B (A * B)."""
    if not a or not a[0] or not b or not b[0]:
        raise ValueError("matrix_multiply: matrices must not be empty.")

    num_rows_a = len(a)
    num_cols_a = len(a[0])
    num_rows_b = len(b)
    num_cols_b = len(b[0])

    for row in a:
        if len(row) != num_cols_a:
            raise ValueError(
                "matrix_multiply: all rows of A must have the same length."
            )
    for row in b:
        if len(row) != num_cols_b:
            raise ValueError(
                "matrix_multiply: all rows of B must have the same length."
            )

    if num_cols_a != num_rows_b:
        raise ValueError(
            "matrix_multiply: number of columns of A must equal number of rows of B."
        )

    result: list[list[float]] = []
    for i in range(num_rows_a):
        row_result = []
        for j in range(num_cols_b):
            value = sum(a[i][k] * b[k][j] for k in range(num_cols_a))
            row_result.append(value)
        result.append(row_result)

    return result


@tool()
async def transpose_matrix(
    matrix: Annotated[
        list[list[float]],
        "Matrix represented as a list of rows; all rows must have the same length",
    ],
) -> list[list[float]]:
    """Transpose a matrix (swap rows and columns)."""
    if not matrix:
        return []
    num_cols = len(matrix[0])
    for row in matrix:
        if len(row) != num_cols:
            raise ValueError(
                "transpose_matrix: matrix rows must all have the same length."
            )

    return [[row[j] for row in matrix] for j in range(num_cols)]


@tool()
async def numerical_derivative(
    x_values: Annotated[
        list[float],
        "Strictly increasing x values where the function is sampled",
    ],
    y_values: Annotated[
        list[float],
        "Function values f(x) corresponding to x_values",
    ],
) -> list[float]:
    """
    Compute a numerical approximation of the derivative f'(x)
    using finite differences (central where possible).
    """
    if len(x_values) != len(y_values):
        raise ValueError(
            "numerical_derivative: x_values and y_values must have the same length."
        )
    n = len(x_values)
    if n < 2:
        raise ValueError("numerical_derivative: at least two points are required.")
    if any(x2 <= x1 for x1, x2 in zip(x_values, x_values[1:])):
        raise ValueError("numerical_derivative: x_values must be strictly increasing.")

    derivatives: list[float] = []
    for i in range(n):
        if i == 0:
            dx = x_values[1] - x_values[0]
            dy = y_values[1] - y_values[0]
        elif i == n - 1:
            dx = x_values[-1] - x_values[-2]
            dy = y_values[-1] - y_values[-2]
        else:
            dx = x_values[i + 1] - x_values[i - 1]
            dy = y_values[i + 1] - y_values[i - 1]
        derivatives.append(dy / dx)
    return derivatives


@tool()
async def numerical_integral_trapezoidal(
    x_values: Annotated[
        list[float],
        "Strictly increasing x values where the function is sampled",
    ],
    y_values: Annotated[
        list[float],
        "Function values f(x) corresponding to x_values",
    ],
) -> float:
    """
    Compute a numerical approximation of the integral of f(x)
    using the trapezoidal rule over the given sample points.
    """
    if len(x_values) != len(y_values):
        raise ValueError(
            "numerical_integral_trapezoidal: x_values and y_values must have the same length."
        )
    n = len(x_values)
    if n < 2:
        raise ValueError(
            "numerical_integral_trapezoidal: at least two points are required."
        )
    if any(x2 <= x1 for x1, x2 in zip(x_values, x_values[1:])):
        raise ValueError(
            "numerical_integral_trapezoidal: x_values must be strictly increasing."
        )

    area = 0.0
    for i in range(n - 1):
        dx = x_values[i + 1] - x_values[i]
        area += 0.5 * dx * (y_values[i] + y_values[i + 1])
    return float(area)


@tool()
async def normal_pdf(
    x: Annotated[
        float, "The point at which to evaluate the normal probability density"
    ],
    mean: Annotated[float, "The mean (mu) of the normal distribution"] = 0.0,
    stddev: Annotated[float, "The standard deviation (sigma), must be > 0"] = 1.0,
) -> float:
    """Compute the probability density function (PDF) of a normal distribution at x."""
    if stddev <= 0:
        raise ValueError("normal_pdf: stddev must be positive.")
    z = (x - mean) / stddev
    return (1.0 / (stddev * sqrt(2.0 * pi))) * exp(-0.5 * z * z)


@tool()
async def normal_cdf(
    x: Annotated[
        float, "The point at which to evaluate the normal cumulative distribution"
    ],
    mean: Annotated[float, "The mean (mu) of the normal distribution"] = 0.0,
    stddev: Annotated[float, "The standard deviation (sigma), must be > 0"] = 1.0,
) -> float:
    """Compute the cumulative distribution function (CDF) of a normal distribution at x."""
    if stddev <= 0:
        raise ValueError("normal_cdf: stddev must be positive.")
    z = (x - mean) / (stddev * sqrt(2.0))
    return 0.5 * (1.0 + erf(z))


@tool()
async def binomial_pmf(
    k: Annotated[int, "Number of successes (0 <= k <= n)"],
    n: Annotated[int, "Number of trials (must be non-negative)"],
    p: Annotated[float, "Probability of success on each trial (0 <= p <= 1)"],
) -> float:
    """Compute the probability mass function (PMF) of a binomial(n, p) at k."""
    if n < 0:
        raise ValueError("binomial_pmf: n must be non-negative.")
    if k < 0 or k > n:
        raise ValueError("binomial_pmf: k must satisfy 0 <= k <= n.")
    if p < 0.0 or p > 1.0:
        raise ValueError("binomial_pmf: p must be in the interval [0, 1].")
    return float(comb(n, k) * (p**k) * ((1.0 - p) ** (n - k)))


@tool()
async def random_uniform(
    low: Annotated[float, "Lower bound of the uniform distribution (inclusive)"],
    high: Annotated[float, "Upper bound of the uniform distribution (exclusive)"],
    size: Annotated[int, "Number of random samples to generate (must be >= 1)"] = 1,
    seed: Annotated[
        Optional[int],
        "Optional random seed for reproducibility; if None, system randomness is used",
    ] = None,
) -> list[float]:
    """Generate samples from a uniform distribution on [low, high)."""
    if high <= low:
        raise ValueError("random_uniform: high must be greater than low.")
    if size < 1:
        raise ValueError("random_uniform: size must be at least 1.")
    rng = random.Random(seed)
    return [rng.uniform(low, high) for _ in range(size)]


@tool()
async def random_normal(
    mean: Annotated[float, "Mean (mu) of the normal distribution"] = 0.0,
    stddev: Annotated[float, "Standard deviation (sigma), must be > 0"] = 1.0,
    size: Annotated[int, "Number of random samples to generate (must be >= 1)"] = 1,
    seed: Annotated[
        Optional[int],
        "Optional random seed for reproducibility; if None, system randomness is used",
    ] = None,
) -> list[float]:
    """Generate samples from a normal (Gaussian) distribution."""
    if stddev <= 0:
        raise ValueError("random_normal: stddev must be positive.")
    if size < 1:
        raise ValueError("random_normal: size must be at least 1.")
    rng = random.Random(seed)
    return [rng.gauss(mean, stddev) for _ in range(size)]


@tool()
async def random_integer(
    low: Annotated[int, "Lower bound of the integer range (inclusive)"],
    high: Annotated[int, "Upper bound of the integer range (inclusive)"],
    size: Annotated[int, "Number of random integers to generate (must be >= 1)"] = 1,
    seed: Annotated[
        Optional[int],
        "Optional random seed for reproducibility; if None, system randomness is used",
    ] = None,
) -> list[int]:
    """Generate random integers uniformly from the inclusive range [low, high]."""
    if high < low:
        raise ValueError("random_integer: high must be greater than or equal to low.")
    if size < 1:
        raise ValueError("random_integer: size must be at least 1.")
    rng = random.Random(seed)
    return [rng.randint(low, high) for _ in range(size)]


@tool()
async def variance_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numeric values for which to compute the variance",
    ],
    sample: Annotated[
        bool,
        "If True, compute the sample variance (divide by n-1); "
        "if False, compute the population variance (divide by n)",
    ] = False,
) -> float:
    """
    Compute the variance of a list of numbers.

    If sample is False (default), this returns the population variance.
    If sample is True, this returns the sample variance (unbiased estimator).
    """
    n = len(numbers)
    if n == 0:
        raise ValueError("variance_value: numbers list must not be empty.")
    if sample and n < 2:
        raise ValueError(
            "variance_value: at least two values are required for sample variance."
        )

    mean = sum(numbers) / n
    sq_diff_sum = sum((x - mean) ** 2 for x in numbers)

    if sample:
        return sq_diff_sum / (n - 1)
    else:
        return sq_diff_sum / n


@tool()
async def median_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numeric values for which to compute the median",
    ],
) -> float:
    """Compute the median (50th percentile) of a list of numbers."""
    n = len(numbers)
    if n == 0:
        raise ValueError("median_value: numbers list must not be empty.")

    sorted_vals = sorted(numbers)
    mid = n // 2

    if n % 2 == 1:
        # Odd number of elements: return the middle one
        return float(sorted_vals[mid])
    else:
        # Even number of elements: average the two middle values
        return float((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)


@tool()
async def quantile_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numeric values from which to compute the quantile",
    ],
    q: Annotated[
        float,
        "Quantile to compute as a value between 0 and 1 (e.g. 0.5 for the median)",
    ],
) -> float:
    """
    Compute the q-th quantile of a list of numbers using linear interpolation.

    q must be in the range [0, 1].
    - q = 0.0 returns the minimum
    - q = 0.5 returns the median (approx.)
    - q = 1.0 returns the maximum
    """
    n = len(numbers)
    if n == 0:
        raise ValueError("quantile_value: numbers list must not be empty.")
    if q < 0.0 or q > 1.0:
        raise ValueError("quantile_value: q must be in the interval [0, 1].")

    sorted_vals = sorted(numbers)
    if n == 1:
        return float(sorted_vals[0])

    # Position in the sorted array (0-based index), using (n - 1) * q
    pos = (n - 1) * q
    lower_idx = int(floor(pos))
    upper_idx = int(ceil(pos))
    if lower_idx == upper_idx:
        return float(sorted_vals[lower_idx])

    weight = pos - lower_idx
    lower_val = sorted_vals[lower_idx]
    upper_val = sorted_vals[upper_idx]
    return float(lower_val + weight * (upper_val - lower_val))


@tool()
async def percentile_value(
    numbers: Annotated[
        list[float],
        "A non-empty list of numeric values from which to compute the percentile",
    ],
    p: Annotated[
        float,
        "Percentile to compute as a value between 0 and 100 (e.g. 50 for the median)",
    ],
) -> float:
    """
    Compute the p-th percentile of a list of numbers using linear interpolation.

    p must be in the range [0, 100].
    This is just a convenience wrapper around quantile_value.
    """
    if p < 0.0 or p > 100.0:
        raise ValueError("percentile_value: p must be in the interval [0, 100].")
    q = p / 100.0
    # Reuse the logic from quantile_value
    n = len(numbers)
    if n == 0:
        raise ValueError("quantile_value: numbers list must not be empty.")
    if q < 0.0 or q > 1.0:
        raise ValueError("quantile_value: q must be in the interval [0, 1].")

    sorted_vals = sorted(numbers)
    if n == 1:
        return float(sorted_vals[0])

    # Position in the sorted array (0-based index), using (n - 1) * q
    pos = (n - 1) * q
    lower_idx = int(floor(pos))
    upper_idx = int(ceil(pos))
    if lower_idx == upper_idx:
        return float(sorted_vals[lower_idx])

    weight = pos - lower_idx
    lower_val = sorted_vals[lower_idx]
    upper_val = sorted_vals[upper_idx]
    return float(lower_val + weight * (upper_val - lower_val))


MATH_TOOLS = [
    # Level 1 – Basic math utilities
    add,
    subtract,
    multiply,
    divide,
    power,
    abs_value,
    sqrt_value,
    nth_root,
    mod,
    floor_value,
    ceil_value,
    round_value,
    min_value,
    max_value,
    # Level 2 – Exponentials, logarithms, trigonometry
    exp_value,
    ln_value,
    log_value,
    sin_value,
    cos_value,
    tan_value,
    deg_to_rad,
    rad_to_deg,
    # Level 3 – Practical statistics
    mean_value,
    stddev_value,
    variance_value,
    median_value,
    quantile_value,
    percentile_value,
    # Level 4 – Basic combinatorics
    factorial_value,
    binomial_coefficient,
    # Level 5 – Core linear algebra
    dot_product,
    matrix_vector_multiply,
    matrix_multiply,
    transpose_matrix,
    # Level 6 – Numerical calculus, distributions, random
    numerical_derivative,
    numerical_integral_trapezoidal,
    normal_pdf,
    normal_cdf,
    binomial_pmf,
    random_uniform,
    random_normal,
    random_integer,
]

# Create the math expert agent with the specified tools and system prompt
math_agent = create_agent(
    math_model,
    tools=MATH_TOOLS,
    system_prompt=SYSTEM_PROMPT_MATH,
)


@tool()
async def math_expert_agent(
    task: Annotated[
        str,
        (
            "Detailed mathematical or statistical problem to solve. "
            "You can include expressions, equations, systems, probability questions, "
            "statistical analysis, linear algebra, numerical calculus or random variables."
        ),
    ],
) -> str:
    """
    Use this tool to delegate complex mathematical or statistical reasoning to a dedicated expert agent.

    The agent can internally orchestrate multiple specialized tools with the following capabilities:

    1) Basic arithmetic and numeric utilities
        - add, subtract, multiply, divide
        - power (x^y), abs_value, sqrt_value, nth_root
        - mod (remainder), floor_value, ceil_value, round_value
        - min_value, max_value
        These allow you to compute and simplify numeric expressions, transform values,
        and prepare inputs for more advanced operations.

    2) Exponentials, logarithms and trigonometry
        - exp_value, ln_value (natural log), log_value (log base b)
        - sin_value, cos_value, tan_value
        - deg_to_rad, rad_to_deg
        Use these for problems involving growth/decay, log transforms, angles,
        periodic functions, and trigonometric identities.

    3) Practical statistics and descriptive analysis
        - mean_value, stddev_value, variance_value
        - median_value, quantile_value, percentile_value
        The agent can summarize datasets, compute dispersion, quantiles and percentiles,
        and support basic descriptive statistics.

    4) Basic combinatorics
        - factorial_value, binomial_coefficient
        Use these for counting problems, discrete probability, and binomial-related questions.

    5) Core linear algebra
        - dot_product
        - matrix_vector_multiply, matrix_multiply
        - transpose_matrix
        The agent can handle vector and matrix operations, such as projections,
        linear transformations, and composing linear systems.

    6) Numerical calculus, probability distributions and random sampling
        - numerical_derivative
        - numerical_integral_trapezoidal
        - normal_pdf, normal_cdf
        - binomial_pmf
        - random_uniform, random_normal, random_integer
        These allow the agent to approximate derivatives and integrals,
        evaluate probabilities and densities for common distributions,
        and generate random samples for simulations or Monte Carlo style reasoning.

    When to use this tool:
     - The problem requires multi-step mathematical reasoning.
     - You need a combination of algebra, statistics, linear algebra, and/or calculus.
     - You want numerically reliable results with optional control over accuracy.
     - You need a structured explanation of the solution steps.

    The agent will:
     - Parse the task, select the appropriate internal tools,
     - Orchestrate multiple calls if necessary,
     - Return a final answer in clear, structured Markdown,

    If the available tools or the provided information are not sufficient to solve the task,
     the agent will state the limitation explicitly instead of inventing results.
    """

    math_messsage = f"""
    Solve the following task:
    ---------------
    {task}
    ---------------
    """
    result = await math_agent.ainvoke(
        {"messages": [{"role": "user", "content": math_messsage}]}
    )
    return result["messages"][-1].content


def load_tools():
    """
    Load tools.
    """
    tools = [
        current_time,
        add_days,
        days_between,
        convert_timezone,
        next_weekday,
        text_cleaner,
        fetch_url,
        get_website_metadata,
        math_expert_agent,
    ]
    if "TAVILY_API_KEY" in os.environ:
        tavily_search = TavilySearch(max_results=5, topic="general")
        tools.append(tavily_search)
    return tools
