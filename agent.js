// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ASCOS

'use strict';

const state = {
  offsetMs: 0,
  freeze: false,
  ticks: false,
};

const hookedAddresses = new Set();
const crtModulePattern = /^(ucrtbase|ucrtbased|msvcrt|msvcrtd|msvcr\d+|msvcr\d+d)\.dll$/;

function log(message) {
  send({ type: 'log', message: message });
}

function findExport(moduleNames, exportName) {
  for (let index = 0; index !== moduleNames.length; index += 1) {
    const module = Process.findModuleByName(moduleNames[index]);
    if (module === null) {
      continue;
    }
    const address = module.findExportByName(exportName);
    if (address !== null) {
      return { moduleName: module.name, address: address };
    }
  }
  return null;
}

function attachOnce(address, callbacks) {
  const key = address.toString();
  if (hookedAddresses.has(key)) {
    return false;
  }
  hookedAddresses.add(key);
  Interceptor.attach(address, callbacks);
  return true;
}

let qpcCall = null;
let qpcFrequency = 1;
let qpcStart = null;
const qpcBuffer = Memory.alloc(8);

function initMonotonic() {
  const counter = findExport(['kernel32.dll'], 'QueryPerformanceCounter');
  const frequency = findExport(['kernel32.dll'], 'QueryPerformanceFrequency');
  if (counter === null || frequency === null) {
    return;
  }
  const frequencyCall = new NativeFunction(frequency.address, 'int', ['pointer']);
  qpcCall = new NativeFunction(counter.address, 'int', ['pointer']);
  frequencyCall(qpcBuffer);
  qpcFrequency = qpcBuffer.readU64().toNumber();
  qpcCall(qpcBuffer);
  qpcStart = qpcBuffer.readU64().toNumber();
}

function elapsedMs() {
  if (qpcCall === null || qpcStart === null) {
    return 0;
  }
  qpcCall(qpcBuffer);
  return (qpcBuffer.readU64().toNumber() - qpcStart) * 1000 / qpcFrequency;
}

function currentOffsetMs() {
  if (!state.freeze) {
    return state.offsetMs;
  }
  return state.offsetMs - elapsedMs();
}

let cachedOffset100ns = null;

function currentOffset100ns() {
  if (!state.freeze && cachedOffset100ns !== null) {
    return cachedOffset100ns;
  }
  const value = BigInt(Math.round(currentOffsetMs())) * 10000n;
  if (!state.freeze) {
    cachedOffset100ns = value;
  }
  return value;
}

function shiftSystemTime(systemTime, deltaMs) {
  const shifted = new Date(Date.UTC(
    systemTime.readU16(),
    systemTime.add(2).readU16() - 1,
    systemTime.add(6).readU16(),
    systemTime.add(8).readU16(),
    systemTime.add(10).readU16(),
    systemTime.add(12).readU16(),
    systemTime.add(14).readU16()
  ) + deltaMs);
  systemTime.writeU16(shifted.getUTCFullYear());
  systemTime.add(2).writeU16(shifted.getUTCMonth() + 1);
  systemTime.add(4).writeU16(shifted.getUTCDay());
  systemTime.add(6).writeU16(shifted.getUTCDate());
  systemTime.add(8).writeU16(shifted.getUTCHours());
  systemTime.add(10).writeU16(shifted.getUTCMinutes());
  systemTime.add(12).writeU16(shifted.getUTCSeconds());
  systemTime.add(14).writeU16(shifted.getUTCMilliseconds());
}

function shiftFileTime(fileTime) {
  const low = BigInt(fileTime.readU32());
  const high = BigInt(fileTime.add(4).readU32());
  let value = (high << 32n) | low;
  value += currentOffset100ns();
  if (value < 0n) {
    value = 0n;
  }
  fileTime.writeU32(Number(value & 0xffffffffn));
  fileTime.add(4).writeU32(Number((value >> 32n) & 0xffffffffn));
}

function hookSystemTimeApi(exportName) {
  const found = findExport(['kernelbase.dll', 'kernel32.dll'], exportName);
  if (found === null) {
    log('atlandi (export yok): ' + exportName);
    return;
  }
  const installed = attachOnce(found.address, {
    onEnter(args) {
      this.target = args[0];
    },
    onLeave() {
      if (!this.target.isNull()) {
        const delta = currentOffsetMs();
        if (delta !== 0) {
          shiftSystemTime(this.target, delta);
        }
      }
    },
  });
  if (installed) {
    log('hook: ' + found.moduleName + '!' + exportName);
  }
}

function hookFileTimeApi(moduleNames, exportName) {
  const found = findExport(moduleNames, exportName);
  if (found === null) {
    log('atlandi (export yok): ' + exportName);
    return;
  }
  const installed = attachOnce(found.address, {
    onEnter(args) {
      this.target = args[0];
    },
    onLeave() {
      if (!this.target.isNull()) {
        shiftFileTime(this.target);
      }
    },
  });
  if (installed) {
    log('hook: ' + found.moduleName + '!' + exportName);
  }
}

function hookTicksApi() {
  const tick = findExport(['kernelbase.dll', 'kernel32.dll'], 'GetTickCount');
  if (tick !== null && attachOnce(tick.address, {
    onLeave(retval) {
      const shifted = (retval.toInt32() + Math.round(currentOffsetMs())) >>> 0;
      retval.replace(ptr(shifted));
    },
  })) {
    log('hook: ' + tick.moduleName + '!GetTickCount');
  }

  const tick64 = findExport(['kernelbase.dll', 'kernel32.dll'], 'GetTickCount64');
  if (tick64 !== null && attachOnce(tick64.address, {
    onLeave(retval) {
      const shifted = Number(retval.toString()) + Math.round(currentOffsetMs());
      if (shifted >= 0) {
        retval.replace(ptr(String(Math.trunc(shifted))));
      }
    },
  })) {
    log('hook: ' + tick64.moduleName + '!GetTickCount64');
  }
}

function inferTimeWidth(moduleName, timeAddress, time32Address, time64Address) {
  if (time64Address !== null && timeAddress.equals(time64Address)) {
    return 8;
  }
  if (time32Address !== null && timeAddress.equals(time32Address)) {
    return 4;
  }
  if (/^msvcrt/.test(moduleName.toLowerCase())) {
    return 4;
  }
  return 0;
}

function hookCrtTime(module, exportName, address, width) {
  if (address === null) {
    return;
  }
  const installed = attachOnce(address, {
    onEnter(args) {
      this.buffer = args[0];
    },
    onLeave(retval) {
      let shifted = Math.trunc(Number(retval.toString()) + currentOffsetMs() / 1000);
      if (shifted < 0) {
        shifted = 0;
      }
      retval.replace(ptr(String(shifted)));
      if (width !== 0 && !this.buffer.isNull()) {
        if (width === 4) {
          this.buffer.writeU32(shifted >>> 0);
        } else {
          this.buffer.writeU64(shifted);
        }
      }
    },
  });
  if (installed) {
    log('hook: ' + module.name + '!' + exportName);
  }
}

function hookCrtModule(module) {
  if (!crtModulePattern.test(module.name.toLowerCase())) {
    return;
  }
  const timeAddress = module.findExportByName('time');
  const time32Address = module.findExportByName('_time32');
  const time64Address = module.findExportByName('_time64');
  if (timeAddress !== null) {
    hookCrtTime(module, 'time', timeAddress,
      inferTimeWidth(module.name, timeAddress, time32Address, time64Address));
  }
  hookCrtTime(module, '_time32', time32Address, 4);
  hookCrtTime(module, '_time64', time64Address, 8);
}

function watchCrtModules() {
  let observerInstalled = false;
  try {
    if (typeof Process.attachModuleObserver === 'function') {
      Process.attachModuleObserver({
        onAdded(module) {
          try {
            hookCrtModule(module);
          } catch (error) {
          }
        },
      });
      observerInstalled = true;
    }
  } catch (error) {
    observerInstalled = false;
  }

  Process.enumerateModules().forEach(function (module) {
    try {
      hookCrtModule(module);
    } catch (error) {
    }
  });

  if (!observerInstalled) {
    let rounds = 0;
    const timer = setInterval(function () {
      Process.enumerateModules().forEach(function (module) {
        try {
          hookCrtModule(module);
        } catch (error) {
        }
      });
      rounds += 1;
      if (rounds >= 120) {
        clearInterval(timer);
      }
    }, 500);
  }
}

rpc.exports = {
  init(config) {
    state.offsetMs = config.fakeUtcMs - Date.now();
    state.freeze = config.freeze === true;
    state.ticks = config.ticks === true;

    initMonotonic();

    hookSystemTimeApi('GetSystemTime');
    hookSystemTimeApi('GetLocalTime');
    hookFileTimeApi(['kernelbase.dll', 'kernel32.dll'], 'GetSystemTimeAsFileTime');
    hookFileTimeApi(['kernelbase.dll', 'kernel32.dll'], 'GetSystemTimePreciseAsFileTime');
    hookFileTimeApi(['ntdll.dll'], 'NtQuerySystemTime');
    if (state.ticks) {
      hookTicksApi();
    }
    watchCrtModules();

    log('offset: ' + Math.round(state.offsetMs) + ' ms' + (state.freeze ? ' (donuk mod)' : ''));
    return { offsetMs: Math.round(state.offsetMs) };
  },
};
