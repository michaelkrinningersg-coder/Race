"""Seed-Verwaltung fuer reproduzierbare Simulationen.

Arbeitsregel: Jede Simulation laeuft mit einem Seed, damit ein Ergebnis
jederzeit exakt wiederholbar ist.

Das GDD wuerfelt an vielen Stellen getrennt (GDD 7 und 11): Wetter, Tagesform
und Eigenschafts-Zufall werden fuer Qualifying und Rennen je einzeln gezogen.
Ein einzelner fortlaufender Zufallsstrom waere dafuer unbrauchbar, weil jede
zusaetzliche Ziehung alle spaeteren Werte verschieben wuerde. Deshalb wird aus
dem Hauptseed je Zweck ein eigener, benannter Strom abgeleitet:

    haupt = Seedquelle(12345)
    wetter = haupt.zweig("saison", 1).zweig("rennen", 3).zweig("wetter")

Zwei Stroeme mit demselben Pfad liefern immer dieselbe Folge, und ein neuer
Zweig laesst alle bestehenden unveraendert.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

import numpy as np

# Der abgeleitete Seed wird auf 64 Bit begrenzt; das reicht fuer numpy und
# laesst sich als ganze Zahl im Spielstand ablegen.
_SEED_BITS = 64
_SEED_BYTES = _SEED_BITS // 8
_SEED_MASKE = (1 << _SEED_BITS) - 1


def _mische(seed: int, pfad: tuple[str, ...]) -> int:
    """Leitet aus Seed und Pfad deterministisch einen neuen Seed ab."""
    quelle = hashlib.blake2b(digest_size=_SEED_BYTES)
    quelle.update(seed.to_bytes(_SEED_BYTES, "big", signed=False))
    for teil in pfad:
        # Die Laenge geht mit ein, damit ("ab", "c") und ("a", "bc")
        # verschiedene Seeds ergeben.
        roh = teil.encode("utf-8")
        quelle.update(len(roh).to_bytes(4, "big"))
        quelle.update(roh)
    return int.from_bytes(quelle.digest(), "big") & _SEED_MASKE


@dataclass(frozen=True)
class Seedquelle:
    """Ein benannter, reproduzierbarer Zufallsstrom.

    :param seed: Hauptseed der Simulation.
    :param pfad: Bezeichnung des Zweigs, z. B. ``("saison:1", "rennen:3")``.
    """

    seed: int
    pfad: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise TypeError("Der Seed muss eine ganze Zahl sein")
        if not 0 <= self.seed <= _SEED_MASKE:
            raise ValueError(f"Der Seed muss zwischen 0 und {_SEED_MASKE} liegen")

    @classmethod
    def zufaellig(cls) -> Seedquelle:
        """Erzeugt einen neuen Hauptseed, etwa beim Start einer Karriere."""
        return cls(secrets.randbits(_SEED_BITS))

    def zweig(self, name: str, *nummern: int) -> Seedquelle:
        """Leitet einen untergeordneten Strom ab.

        ``zweig("rennen", 3)`` ergibt den Pfadteil ``"rennen:3"``.
        """
        if not name:
            raise ValueError("Ein Zweig braucht einen Namen")
        teil = ":".join((name, *(str(n) for n in nummern)))
        return Seedquelle(self.seed, (*self.pfad, teil))

    @property
    def abgeleiteter_seed(self) -> int:
        """Der aus Hauptseed und Pfad berechnete Seed dieses Zweigs."""
        return _mische(self.seed, self.pfad)

    def generator(self) -> np.random.Generator:
        """Liefert einen frischen NumPy-Generator fuer diesen Zweig.

        Jeder Aufruf beginnt die Folge von vorn, der Zweig ist damit beliebig
        oft wiederholbar.
        """
        return np.random.default_rng(self.abgeleiteter_seed)

    @property
    def bezeichnung(self) -> str:
        """Lesbare Form fuer Debug-Ansicht und Protokolle."""
        return "/".join(("seed:" + str(self.seed), *self.pfad))

    def __str__(self) -> str:
        return self.bezeichnung
