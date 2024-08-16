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

def adjust_quantity(quantity, min_volume, tick):
    quantity = Decimal(str(quantity))
    min_volume = Decimal(str(min_volume))
    tick = Decimal(str(tick))

    # Приводим количество к кратному значению tick
    adjusted_quantity = (quantity // tick) * tick

    # Проверяем, меньше ли полученное значение минимального объема
    if adjusted_quantity < min_volume:
        return -1

    return float(adjusted_quantity)

def round_price(price, tick_size):
    price = Decimal(str(price))
    tick_size = Decimal(str(tick_size))
    return float((price // tick_size) * tick_size)