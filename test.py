from scrapling import StealthyFetcher

page = StealthyFetcher.fetch(
    "https://qatarsale.com/ar/product/toyota_land_cruiser_gxr_2024_white_automatic_suv-541319",
    headless=True,
    network_idle=True,
)

listing = page.find("[data-testid='at-show-product-info-forSale-text']")
showroom = page.find("[data-testid='at-show-product-info-showroom-name-text']")

print("listing:", str(listing) if listing else "MISSING")
print("showroom:", str(showroom) if showroom else "MISSING")