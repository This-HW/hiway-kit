from legacy import old_api


class Widget:
    def old_api(self, x):
        return x + 100


def use():
    w = Widget()
    # method homonym must not be rewritten: w.old_api(1)
    return w.old_api(1) + old_api(10)
