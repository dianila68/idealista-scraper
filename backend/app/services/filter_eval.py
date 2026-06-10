from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing


def matches(listing: RawListing, fc: FilterConfig) -> bool:
    """Return True if *listing* satisfies every constraint in *fc*.

    Missing listing fields (None) pass any constraint on that dimension —
    the scraper may not have extracted the field.
    """
    if fc.listing_type and listing.listing_type and listing.listing_type != fc.listing_type:
        return False

    if fc.property_type and listing.property_type and listing.property_type not in fc.property_type:
        return False

    if fc.locations and listing.city:
        cities = [loc.city.lower() for loc in fc.locations]
        if listing.city.lower() not in cities:
            return False
        # Zone check — only if the matching location specifies zones
        for loc in fc.locations:
            if loc.city.lower() == listing.city.lower() and loc.zones and listing.zone:
                zones_lower = [z.lower() for z in loc.zones]
                if listing.zone.lower() not in zones_lower:
                    return False

    if listing.price is not None:
        if fc.price.min is not None and listing.price < fc.price.min:
            return False
        if fc.price.max is not None and listing.price > fc.price.max:
            return False

    if listing.size_sqm is not None:
        if fc.size_sqm.min is not None and listing.size_sqm < fc.size_sqm.min:
            return False
        if fc.size_sqm.max is not None and listing.size_sqm > fc.size_sqm.max:
            return False

    if listing.rooms is not None:
        if fc.rooms.min is not None and listing.rooms < fc.rooms.min:
            return False
        if fc.rooms.max is not None and listing.rooms > fc.rooms.max:
            return False

    if listing.bathrooms is not None:
        if fc.bathrooms.min is not None and listing.bathrooms < fc.bathrooms.min:
            return False
        if fc.bathrooms.max is not None and listing.bathrooms > fc.bathrooms.max:
            return False

    if listing.floor is not None:
        if fc.floor.min is not None and listing.floor < fc.floor.min:
            return False
        if fc.floor.exclude_ground and listing.floor == 0:
            return False

    if fc.features:
        listing_features = {f.lower() for f in listing.features}
        for required in fc.features:
            if required.lower() not in listing_features:
                return False

    return not (fc.sources and listing.source not in fc.sources)


def matching_filter_ids(
    listing: RawListing,
    filters: list[tuple[str, FilterConfig]],
) -> list[str]:
    """Return the IDs of all filters that *listing* satisfies."""
    return [fid for fid, fc in filters if matches(listing, fc)]
