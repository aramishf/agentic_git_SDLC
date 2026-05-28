def calculate_average(numbers):
    # BUG: This will raise ZeroDivisionError if numbers is empty.
    # The requirement is: return 0.0 for empty lists.
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)