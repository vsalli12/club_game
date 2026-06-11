from holdable import Holdable

class Item(Holdable):
    def __init__(self, app, owner, **kwargs):
        super().__init__(app, owner, **kwargs)
        self.name = kwargs.get('name', "Item")
        self.price = kwargs.get('price', 10)
        self.description = kwargs.get('description', "Misc")
