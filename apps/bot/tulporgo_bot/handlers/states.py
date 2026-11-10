from aiogram.fsm.state import State, StatesGroup


class Order(StatesGroup):
    place = State()        # picking a place (buttons, or typing a name to search); data["role"] = f | t
    time = State()
    seats = State()
    note = State()
    confirm = State()


class Offer(StatesGroup):
    price = State()        # driver types a custom price; data["rid"]


class Counter(StatesGroup):
    price = State()        # passenger types a counter price; data["oid"]


class Reg(StatesGroup):    # driver registration
    phone = State()
    make = State()
    color = State()
    plate = State()
    seats = State()
    photo = State()
    home = State()         # place picker (role h); typing searches


class Docs(StatesGroup):
    license = State()
    techpass = State()


class Complaint(StatesGroup):
    text = State()         # data["trip_id"] (0 = none)


class Admin(StatesGroup):
    block = State()        # admin types a user id or @username
