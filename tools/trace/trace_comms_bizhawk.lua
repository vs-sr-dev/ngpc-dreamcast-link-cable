-- trace_comms_bizhawk.lua
-- BizHawk Lua script — trace NGPC BIOS comms vector hits on retail ROMs
-- Goal: decide if the ROM uses the canonical SDK BIOS vectors (BIOS-HLE path)
--        or if it pokes the TLCS-900H UART registers directly (MAME transplant path).
--
-- How to use:
--   1. Open BizHawk, load the target NGPC ROM (e.g. SNK vs Capcom: Match of the Millennium).
--   2. Tools → Lua Console → Open Script… → select this file.
--   3. Click "Run" — script starts listening. Initial message "[trace_comms] armed..." appears.
--   4. In-game, navigate to the LINK / VS / NETWORK MATCH / 通信対戦 menu and try to initiate a link.
--      (It will fail — no peer attached — but should trigger at least one comms vector call.)
--   5. Watch the Lua Console. Every hit prints one line and appends to trace_comms_log.txt
--      next to the ROM.
--   6. Report back what got logged (or: "nothing logged after entering link menu").
--
-- Interpretation:
--   - ≥1 vector fired → BIOS path → BIOS-HLE strategy (patch the emulator's comms hooks).
--   - Zero vectors fired WITH confirmed link-menu navigation → likely register-level poke
--     → escalate to MAME debugger with SC0BUF watchpoint.
--   - Some vectors fired but not others → partial BIOS usage, hybrid strategy possible.

local vectors = {
    [0xFF2C86] = "VECT_COMCREATEDATA",
    [0xFF2CB4] = "VECT_COMGETDATA",
    [0xFF2D27] = "VECT_COMONRTS",
    [0xFF2D33] = "VECT_COMOFFRTS",
    [0xFF2D3A] = "VECT_COMSENDSTATUS",
    [0xFF2D4E] = "VECT_COMRECIVESTATUS",
    [0xFF2D6C] = "VECT_COMCREATEBUFDATA",
    [0xFF2D85] = "VECT_COMGETBUFDATA",
}

local hit_counts = {}
for addr, _ in pairs(vectors) do hit_counts[addr] = 0 end

local log_path = "trace_comms_log.txt"
local log_file = io.open(log_path, "w")
if log_file then
    log_file:write(string.format("# trace_comms_bizhawk.lua — session start frame %d\n", emu.framecount()))
    log_file:flush()
end

local function on_hit(addr)
    hit_counts[addr] = hit_counts[addr] + 1
    local name = vectors[addr]
    local frame = emu.framecount()
    local line = string.format("[frame %d] HIT %s (0x%06X) count=%d",
                               frame, name, addr, hit_counts[addr])
    console.log(line)
    if log_file then
        log_file:write(line .. "\n")
        log_file:flush()
    end
end

-- event.onmemoryexecute registers a callback fired when the CPU executes at the address.
-- The "System Bus" domain is the CPU-visible bus (includes BIOS ROM region 0xFF0000+).
-- If the NGPC Nyma core in your BizHawk version doesn't expose System Bus for execute
-- events, the pcall below will fail cleanly and the script will fall back to a
-- per-frame PC poll (less reliable but better than nothing).

local ok_all = true
for addr, name in pairs(vectors) do
    local ok, err = pcall(function()
        event.onmemoryexecute(function() on_hit(addr) end, addr, "trace_" .. name, "System Bus")
    end)
    if not ok then
        ok_all = false
        console.log(string.format("[trace_comms] onmemoryexecute failed for %s: %s", name, tostring(err)))
    end
end

if ok_all then
    console.log("[trace_comms] armed: 8 BIOS vectors under watch. Navigate to link menu.")
else
    console.log("[trace_comms] partial arm — some hooks failed. Check BizHawk version / domain support.")
    console.log("[trace_comms] fallback: per-frame PC polling (coarse, may miss fast transitions).")

    -- Fallback: poll PC each frame. Uses emu.getregisters() which returns a table of CPU regs.
    -- TLCS-900H register name may be "PC" or "pc" depending on core version.
    local function poll()
        local regs = emu.getregisters()
        if regs == nil then return end
        local pc = regs.PC or regs.pc
        if pc == nil then return end
        if vectors[pc] then on_hit(pc) end
    end
    event.onframeend(poll)
end

event.onexit(function()
    if log_file then
        log_file:write("# session end\n")
        log_file:write("# hit summary:\n")
        for addr, name in pairs(vectors) do
            log_file:write(string.format("#   %s (0x%06X): %d hits\n", name, addr, hit_counts[addr]))
        end
        log_file:close()
    end
    console.log("[trace_comms] log saved to " .. log_path)
end)
