def load_吾輩は猫である(path="./scripts/吾輩は猫であるutf8.txt") -> list[str]:
    with open(path, encoding="utf8") as f:
        lines = f.readlines()
        
    return lines