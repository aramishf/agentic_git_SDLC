def calculate_average(numbers):
    # Returns 0.0 for an empty list, as per requirement.
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)