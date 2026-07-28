from . import (
    amazon,
    ashby,
    eightfold,
    google,
    greenhouse,
    lever,
    microsoft,
    simplify,
    smartrecruiters,
    uber,
    workday,
)

REGISTRY = {
    "greenhouse": greenhouse.fetch,
    "ashby": ashby.fetch,
    "lever": lever.fetch,
    "workday": workday.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "amazon": amazon.fetch,
    "eightfold": eightfold.fetch,
    "uber": uber.fetch,
    "microsoft": microsoft.fetch,
    "google": google.fetch,
    "simplify": simplify.fetch,
}

__all__ = ["REGISTRY"]
