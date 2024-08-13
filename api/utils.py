from decimal import Decimal, ROUND_DOWN


def calculate_purchase_volume(sum_amount, price, min_volume, tick):
    sum_amount = Decimal(str(sum_amount))
    price = Decimal(str(price))
    min_volume = Decimal(str(min_volume))
    tick = Decimal(str(tick))

    volume = sum_amount / price
    rounded_volume = (volume // tick) * tick

    if rounded_volume < min_volume:
        return -1

    return float(rounded_volume.quantize(tick, rounding=ROUND_DOWN))

def round_price(price, tick_size):
    price = Decimal(str(price))
    tick_size = Decimal(str(tick_size))
    return float((price // tick_size) * tick_size)