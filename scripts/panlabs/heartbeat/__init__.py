"""O heartbeat da máquina: hospedeiro de passos plugáveis, poda e alarmes.

O disparo mora no agendador do host, porque é o único relógio que corre com o
WSL desligado e o único lugar de onde o disco real do host é visível.
"""
