def find_duplicates(items):
    """items에서 중복으로 등장하는 값들을 반환한다(순서 무관, 중복 없이)."""
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates
