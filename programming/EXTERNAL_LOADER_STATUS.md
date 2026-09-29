# External loader status (STM32CubeProgrammer `.stldr`) - firmware 0.2.1

**Status: BUILT + STRUCTURALLY VERIFIED, NOT HARDWARE QUALIFIED.** The loader in this package has
never erased, programmed or read the NOR of an assembled board. Before production use, engineering
must pass the first-board qualification in section 6.

## 1. What the packaged loader is

The STM32N657 has no internal flash. The FSBL and the test application live in the external
octal NOR U2 (Macronix **MX25UM25645GXDI00**, 256 Mbit = 32 MiB), which sits on XSPI2 through
XSPIM port 2, chip select NCS1. STM32CubeProgrammer can write this memory only through an
external loader: a program that it downloads into MCU SRAM over SWD and then calls.

`programming/external_loader.stldr` is the **board loader `MX25UM25645G_STM32N657_FC`**, built
from `07_EXTERNAL_LOADER/` in the source bundle. That directory holds the ST ExtMemLoader template
completed for this board, and the ST middleware `stm32-mw-extmem-ldr` v1.1.2 and
`stm32-mw-extmem-mgr`, compiled unmodified from `vendor/`. A `.stldr` file is the loader ELF.
`PROGRAM_JLCPCB.bat` and `VERIFY_JLCPCB.bat` use this file by default.

At packaging time, `05_TOOLS/package_jlc.py` appends the section **"Packaged loader identity"** at
the end of this file. It holds the SHA-256, the firmware build id and the structural verification
verdict. `05_TOOLS/verify_package.py` checks that this SHA-256 matches the packaged file. If
the section is missing, the package was produced with `--docs-only` and is not a station package.

## 2. Configuration summary

| Item | Value |
|---|---|
| DeviceName / type | `MX25UM25645G_STM32N657_FC`, NOR_FLASH |
| Start / size | `0x70000000` / `0x02000000` (32 MiB) |
| Sectors | 512 x 64 KiB (`0x10000`) |
| PageSize / EraseValue | `0x1000` (CubeProgrammer programming granularity; the driver splits every write at the 256-byte device page) / `0xFF` |
| XSPI2 | `HAL_XSPI_SIZE_256MB` (HAL sizes are megabits), Macronix, NCS1, XSPIM port 2, pins PN0-PN6 and PN8-PN11 (AF9) |
| Kernel clock | fixed 50 MHz (IC3 = PLL1 1200 MHz / 24); the VDDIO3_HSLV OTP fuse is never read |
| Identity required at `Init()` | kernel clock 50 MHz, `EXTMEM_Init` = OK, manufacturer ID 0xC2, SFDP density 2^25, SFDP page 256 bytes |
| Error propagation | strong `memory_*` hooks: after any init failure, `Init()` returns 0 and every Write/SectorErase/MassErase returns 0, so no NOR command reaches a device that failed to start or to identify. The status structure `fc_loader_status` can be read over SWD (address: `engineering/LOADER_VERIFICATION.txt`) |
| Safety | PA3 (MOTOR_ENABLE) is driven LOW first; PN12 (PSRAM NCS2) is never driven; no OTP access; no DMA or interrupts; every wait is bounded |
| Cache | D-cache off (no stale data between indirect and memory-mapped access); I-cache on, as in the ST template |

Full details are in `07_EXTERNAL_LOADER/README.md` sections 3-8.

## 3. Verification status

| Level | Result |
|---|---|
| IMPLEMENTED | loader sources complete, built with zero compiler/linker warnings |
| TOOL-VERIFIED | `05_TOOLS/verify_loader.py`, structural only: API symbols, strong error hooks, StorageInfo placement and content against the values above, `.stldr` = ELF, comparison with ST's NUCLEO loader. Report: `engineering/LOADER_VERIFICATION.txt` (`OVERALL: PASS`). Host test `loader_storageinfo`: `engineering/HOST_TEST_REPORT.txt` |
| HARDWARE-VERIFIED | **nothing.** A structural check cannot show that the loader erases or programs U2 |

## 4. Programmed ranges

| Image (package file) | Start | Last byte (inclusive) |
|---|---|---|
| `firmware/FC_FSBL_LRUN_Trusted.bin` | `0x70000000` | `0x70000000` + file size - 1 (inside the first 64 KiB block) |
| `firmware/FC_Manufacturing_Test_Trusted.bin` | `0x70100000` | `0x70100000` + file size - 1 |

The file sizes are listed in `MANIFEST.txt`, and under `[artifacts]` in `firmware/VERSION.txt`
(as `FSBL-trusted.bin` / `App-trusted.bin`). The 0.2.1 application image ends below
`0x70120000`: it fits in the two 64 KiB sectors at 0x70100000 and 0x70110000. The hard limit is
the FSBL copy size of 0x40000 bytes, which `verify_images.py` checks, so the application range
can never pass `0x7013FFFF`.
**The 0.2.0 documents said "0x7010FFFF" at most. That was wrong for 0.2.x images**: the external
audit found the 0.2.0 application already ending at 0x70115D3F.

Before writing, STM32CubeProgrammer erases the 64 KiB sectors the range touches. One extra
sector may be erased (section 8). The 64 KiB block after each image is unused, so the current
layout tolerates that. `VERIFY_JLCPCB.bat` reads back exactly the file size at each start
address.

## 5. Connect under reset (default)

`PROGRAM_JLCPCB.bat`, `VERIFY_JLCPCB.bat` and `05_TOOLS/program_dev.bat` connect with
`FC_CONNECT_OPTS=mode=UR` unless the variable is set.

The reason: the loader is downloaded into the same SRAM that the FSBL runs from. If the FSBL or
the application is running and has enabled the I-cache, that cache can hold stale lines for the
addresses the loader was just written to. `SCB_EnableICache()` does not invalidate a cache that
is already enabled, and the loader cannot protect itself against this. After a reset the I-cache
is disabled, and the loader's `SCB_EnableICache()` invalidates it before switching it on.

Therefore **hot-plug connection (`mode=HOTPLUG`) is not supported for loader operations.**
(`READ_DIAG_LOG.bat read` uses hot-plug on purpose, without a loader, only to read RAM.) Any
other connect mode, and whether a blank board needs BOOT1 = 1 (development boot), are
**TBD - first-board qualification** (section 6, step 2).

## 6. First-board qualification procedure (engineering; nothing below has been done)

The authoritative text is `07_EXTERNAL_LOADER/README.md` section 9. The commands use
`STM32_Programmer_CLI`, with `<loader>` = `programming\external_loader.stldr`. That file is
identical to `build\MX25UM25645G_STM32N657_FC.stldr`. Setup: no ESC/motor/propeller, SWD probe
on J20, UART adapter on J4 (115200 8N1), bench supply with current limit. Record every command
and its full output (`-vb 3` and/or `-log <file>`).

1. **Record the setup.**
   - Record the `STM32_Programmer_CLI --version` output.
   - Record the loader SHA-256 (`certutil -hashfile <loader> SHA256`). It must equal the identity
     section below and the `sha256` line of `engineering/LOADER_VERIFICATION.txt`, which must
     end with `OVERALL: PASS`.
   - Record the board serial, the BOOT1/J28 state, the supply current, and `MOTOR_OE_N` (must be
     high).
2. **Connect** with `-c port=SWD mode=UR -el <loader> -vb 3`.
   - Record whether the connection needed BOOT1 = 1 (development boot; J28 connects PA6/BOOT1 to
     VDD3V3). This result decides the station fixture. J28 must be open again for every boot
     test.
   - The log should name the loader `MX25UM25645G_STM32N657_FC`, at 0x70000000, 32 MiB.
3. **Init and read** with `-r32 0x70000000 0x40`.
   - A blank NOR reads `0xFFFFFFFF`. A programmed NOR reads the bytes `53 54 4D 32`, which
     `-r32` displays as the word `0x324D5453`.
   - If `Init` fails: read `fc_loader_status` over SWD at once, with no reset in between
     (`-c port=SWD mode=HOTPLUG -r32 <addr> 0x48`). Record `error_mask`, `manu_id`,
     `flash_size_pow2`, `page_size`, `erase_size[]` and `xspi_kernel_hz`, then **stop**.
   - If `Init` passes: record `erase_size[]` all the same.
4. **Scratch-block erase.**
   - Use blocks **496 and 497** (`0x71F00000`-`0x71F1FFFF`); the images never use them.
   - Run `-e [496 497]`. If erase by index is not accepted, let the step-5 writes erase and
     record which case happened.
   - Read back with `-u 0x71F00000 0x20000 erased.bin`: every byte must be `0xFF`.
5. **Pattern write, read-back, verify.**
   - Write a 64 KiB file in which each 32-bit word = its own offset XOR `0xA5A5A5A5`, at
     `0x71F00000` with `-v`. Read it back with `-u` and compare with `fc /b`.
   - **Even-address page-split probe:** write a 300-byte `split.bin` (non-`0xFF` content) at
     `0x71F10080` with `-v`. It crosses the 256-byte page at `0x71F10100`, and both its address
     and its length are even, as DTR-OPI requires. Read it back and compare.
6. **Erase verify and erase boundary.**
   - Run `-e [496 496]`. `0x71F00000` + 64 KiB must read all `0xFF`.
   - `0x71F10080` (300 B) must still equal `split.bin`. If block 497 was erased as well, record
     "sector erase erases one extra sector" (section 8).
   - Erase block 497 and check that it reads all `0xFF`.
7. **Program the images** with `-w <FSBL> 0x70000000 -v` and `-w <App> 0x70100000 -v` (what
   `PROGRAM_JLCPCB.bat` runs).
8. **Full read-back.** Compare both ranges byte for byte (what `VERIFY_JLCPCB.bat` runs). Also
   read the first 64 KiB after the end of each image: it must be `0xFF` where erased.
9. **Cold power-cycle boot.**
   - Disconnect the probe or switch it off, remove board power for >= 5 s, then power on.
   - Capture the console. `FSBL: reached ...` and the application banner must appear.
   - Evaluate the capture with `diagnostics\CHECK_UART_LOG.bat` (= `parse_station_log.py`).
10. **Record and decide.**
    - Keep the CubeProgrammer version, the loader SHA-256, all CLI logs, read-back files and
      hashes, the console capture, `fc_loader_status` (if read), the connect mode and the
      BOOT1 state.
    - The loader counts as **qualified for this board revision only** if steps 2-9 pass on at
      least the first boards.
    - Then update `07_EXTERNAL_LOADER/README.md`, `01_HARDWARE_HANDOFF/STATION_FACTS_0.2.1.md`
      and this status, and regenerate the package.

Never part of the procedure: mass erase (`-e all`, up to 150 s, not needed), and the OTP loader
`OTP_FUSES_STM32N6xx.stldr`.

## 7. ST's NUCLEO loader (not the default)

`MX25UM51245G_STM32N6570-NUCLEO.stldr` ships in the STM32CubeProgrammer installation
(`bin\ExternalLoader\`). It is **not in this package and is no longer the default** anywhere.
It is used only for comparison: as the reference of `verify_loader.py`, and for engineering runs
through `program_dev.bat` with `FC_EXTLOADER`.

| | NUCLEO loader | board loader (packaged) |
|---|---|---|
| Memory | MX25UM51245G, **512 Mbit** | MX25UM25645G, 256 Mbit |
| DeviceSize / sectors | `0x04000000` (**64 MiB**) / 1024 x 64 KiB | `0x02000000` (32 MiB) / 512 x 64 KiB |
| Start / page / erase value | 0x70000000 / 0x1000 / 0xFF | same |
| Init failures | weak ST hooks: ignored | propagated (section 2) |
| Identity / size check | none. It would accept 0x72000000-0x73FFFFFF, addresses that do not exist on U2 | 0xC2, 2^25, page 256 required |
| XSPI clock / D-cache | fuse-dependent / on | 50 MHz fixed / off |

Other loaders in the installation: `MX66UW1G45G_STM32N6570-DK.stldr` is for a different device
and does not apply. `OTP_FUSES_STM32N6xx.stldr` must never be used.

## 8. Known limitations

- **Even address and length in DTR-OPI.** A page program must start at an even address and
  have an even length. The driver splits writes only at the 256-byte page boundary. Odd writes
  are unsupported and untested. The trusted images start on a sector boundary and are whole
  multiples of 16 bytes.
- **Block-protection (BP) bits are not cleared.** They are 0 as delivered. A protected block
  silently ignores erase and program, and only a verify or read-back shows it. That is why
  `VERIFY_JLCPCB.bat` must exit 0.
- **The NOR is left in the driver's octal mode.** Only a boot after a cold power cycle is
  covered by the qualification (step 9). A warm reset right after programming is not.
- **CubeProgrammer erase end address.** The loader keeps ST's erase loop. If CubeProgrammer
  passes an address inside the last sector as the end, **one extra sector** is erased. The
  current layout tolerates this (section 4). Step 6 settles which case happens.
- `Verify()` after a failed `Init()` is not guarded; that is vendor code. CubeProgrammer stops
  when `Init()` returns 0.
- The SFDP content of U2 (erase types and times) is unknown until it is read on a board
  (`fc_loader_status.erase_size[]`).
- ECC works on 16-byte chunks. Program each region once after an erase, which is
  CubeProgrammer's normal erase-then-write flow.
- Hot-plug connection is not supported for loader operations (section 5).

## 9. If qualification fails

- **`Init()` fails:** each `fc_loader_status.error_mask` bit names the failing step
  (`07_EXTERNAL_LOADER/README.md` section 6). Engineering fixes the loader in
  `07_EXTERNAL_LOADER`, rebuilds it, re-runs `verify_loader.py`, and repeats the qualification
  from step 1.
- **Erase, program, verify or boot fails while `Init()` passes:** keep all logs and read-back
  files. Engineering may run ST's NUCLEO loader (section 7) at the same addresses, all below
  0x72000000, as a comparison to locate the fault. Before it could ever be packaged, it would
  need the full qualification itself, and it has no identity check.
- **Until a loader passes qualification**, the package must not be released to JLCPCB for
  production. JLCPCB is never asked to build, modify or choose a loader.
- **After a successful qualification:** regenerate the package with `05_TOOLS/package_jlc.py`
  (the identity section is refreshed), run `05_TOOLS/verify_package.py`, and ship the
  qualification evidence with it.

## Packaged loader identity (generated by 05_TOOLS/package_jlc.py)

| Item | Value |
|---|---|
| File | `programming/external_loader.stldr` (= `build/MX25UM25645G_STM32N657_FC.stldr`) |
| SHA-256 | `84e0993d3ac1115e70a49640c1ba3de28e1b2da789e996390bf353c21a6be9e6` |
| Source | `07_EXTERNAL_LOADER/` of firmware build `src-3bac755b6796` |
| Structural verification | `engineering/LOADER_VERIFICATION.txt`: OVERALL PASS |
| Hardware qualification | **NOT DONE** - see the qualification procedure above |
