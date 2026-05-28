from calculator import calculate_average

def test_calculate_average():
    assert calculate_average([1, 2, 3]) == 2.0

def test_calculate_average_empty():
    assert calculate_average([]) == 0.0
