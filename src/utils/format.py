def _a(count):
    return '*' * count

def comment_block(txt):
    l = len(txt)*2
    return _a(l) + '\n*\t' + txt + '\n' + _a(l) + "\n"
