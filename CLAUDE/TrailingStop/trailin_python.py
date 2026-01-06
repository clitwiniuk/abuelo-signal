import numpy as np
import matplotlib.pyplot as plt

class SpringTrailingStop:
    def __init__(self, entry_price, direction=1, k=0.5, c=0.3, base_dist=0.02):
        self.direction = direction
        self.k = k
        self.c = c
        self.base_dist = base_dist * entry_price

        # estado dinámico del stop
        self.stop = entry_price - self.base_dist if direction==1 else entry_price + self.base_dist
        self.v_stop = 0.0  # velocidad

    def update(self, price, dt=0.1):
        if self.direction == 1:  # long
            dist = price - self.stop - self.base_dist
            force = self.k * dist - self.c * self.v_stop
            a = force
            self.v_stop += a * dt
            self.stop += self.v_stop * dt

            # nunca retroceder más de base_dist
            if self.stop < price - self.base_dist:
                self.stop = price - self.base_dist
                self.v_stop = 0.0
            exit_signal = price <= self.stop
        else:  # short
            dist = self.stop - price - self.base_dist
            force = self.k * dist - self.c * self.v_stop
            a = force
            self.v_stop += a * dt
            self.stop += self.v_stop * dt

            if self.stop > price + self.base_dist:
                self.stop = price + self.base_dist
                self.v_stop = 0.0
            exit_signal = price >= self.stop
        return self.stop, exit_signal

# --- Precio de prueba: sube lento → baja → sube fuerte → cae ---
t = np.linspace(0, 50, 500)
price = np.piecewise(
    t,
    [t < 15, (t>=15)&(t<25), (t>=25)&(t<40), t>=40],
    [
        lambda x: 100 + 0.2*(x-0),
        lambda x: 103 - 0.2*(x-15),
        lambda x: 101 + 0.8*(x-25),
        lambda x: 113 - 1.5*(x-40)
    ]
)

# --- Trailing stop estilo muelle ---
st = SpringTrailingStop(entry_price=price[0], direction=1, k=0.5, c=0.3, base_dist=0.02)
stops = []

for p in price:
    s,_ = st.update(p, dt=0.1)
    stops.append(s)

# --- Graficar ---
plt.figure(figsize=(10,5))
plt.plot(t, price, label="Precio")
plt.plot(t, stops, label="Spring Trailing Stop", linestyle="--", color="red")
plt.xlabel("Tiempo")
plt.ylabel("Precio")
plt.title("Trailing Stop tipo muelle (inercia real, más fluido)")
plt.legend()
plt.grid(True)
plt.show()
