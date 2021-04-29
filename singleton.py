
def singleton(cls, *args, **kwargs):
    __instance = {}

    def __singleton(*args, **kwargs):
        if cls not in __instance:
            __instance[cls] = cls(*args, **kwargs)
        else:
            pass
        return __instance[cls]

    return __singleton
