# Calandria · Flasher

Grabá o actualizá el firmware de los dispositivos **Calandria** desde el navegador, por USB, sin
instalar nada: **https://proto-hommer.github.io/calandria-flasher/**

Hace falta **Chrome o Edge en una computadora** (usan Web Serial; Firefox y Safari no lo tienen).

## Dispositivos

| Dispositivo | Firmware |
|---|---|
| Calandria MK1 epaper | [proto-hommer/calandria-mk1-epaper](https://github.com/proto-hommer/calandria-mk1-epaper) |

## Cómo se usa

1. Enchufá el nodo con un cable USB-C de datos y elegí el dispositivo.
2. **Actualizar**: graba solo la app nueva y conserva el grupo, los canales y la configuración. Cuando el
   instalador pregunte *"Erase device"*, dejá la casilla sin marcar.
3. **Instalación limpia**: borra toda la memoria y graba la imagen completa. Para un nodo nuevo o trabado.
4. Si no aparece el puerto: mantené apretado BOOT, enchufalo (o apretá RESET) y soltá BOOT.

## Cómo funciona

- La página usa [ESP Web Tools](https://esphome.github.io/esp-web-tools/) (Apache-2.0).
- `devices.json` lista los dispositivos de la familia: el repo de cada firmware, el chip y dónde va
  cada parte en la memoria.
- Una GitHub Action (`.github/workflows/pages.yml`) corre `scripts/build_site.py` cada hora, al cambiar
  algo en `main`, o a mano desde Actions. Baja el último release de cada repo, arma los manifiestos y
  publica todo en GitHub Pages. Los `.bin` se copian al sitio porque el navegador no puede bajarlos
  directo de los releases de GitHub (no tienen CORS).
- **Actualizar** graba `firmware-*.bin` en la partición `app0` (0x10000) y repone el selector
  de arranque (`otadata`, 0xE000) igual que en la imagen de fábrica. Así el nodo arranca la app nueva aunque antes se haya actualizado por
  Bluetooth (OTA) desde la otra ranura. La configuración (LittleFS) no se toca.
- **Instalación limpia** borra toda la flash y graba `firmware-*.factory.bin` en 0.

### Sumar un dispositivo

Agregá una entrada a `devices.json`:

- `repo`: el repo de su firmware, con releases que traigan un `.bin` y un `.factory.bin`;
- `asset_prefix`: con qué empiezan sus archivos;
- `chip`: `ESP32-S3`, `ESP32`, etc.;
- `app_offset` y `otadata_offset`/`otadata_size`: salen de su tabla de particiones.

Para probar en la compu: `python3 scripts/build_site.py`, después `python3 -m http.server -d _site`, y abrí
http://localhost:8000 (Web Serial también anda en localhost).

## Licencia

GPL-3.0. powered by Meshtastic®. Meshtastic® es una marca registrada de Meshtastic LLC. Calandria es un
proyecto independiente, no patrocinado ni respaldado por el proyecto Meshtastic.
