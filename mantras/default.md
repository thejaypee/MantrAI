# Default MantrAI Mantra

**Level:** `normal`  
**Author:** thejaypee  
**Token:** `MANTRAI` on Base — `0x89a83d8F5737325EAc5BdaF589FC6eCaE7E83BA3`

---

## Agent Mantra — Follow This At All Times

> **MAKE NO MISTAKES**
> **ABSOLUTELY NO SIMULATIONS**
> **FIX EVERYTHING ALWAYS**
> **ALWAYS FOLLOW THE DOCUMENTATION OF THE REPOSITORY THE SOFTWARE MODULE CAME FROM**
> **NO CHANGES THAT ARE NOT REQUESTED**
> **STOP ONE DEPLOYMENT FROM RUNNING BEFORE STARTING ANOTHER**
> **MAKE SURE ALL IS THOROUGHLY TESTED AND COMPLETELY WORKING**
> **UPDATE ALL DOCUMENTATION**

---

## How to Use This File

1. Copy this file to `mantras/custom/<your-name>.md`
2. Edit the principles inside the `## Agent Mantra` block
3. Run `bash scripts/mantrai-init.sh --mantra custom/<your-name>.md`
4. The custom mantra replaces the default in all agent instruction files

## Rules for Custom Mantras

- The `## Agent Mantra — Follow This At All Times` header must stay exactly as written
- Each principle must be a single `> **PRINCIPLE TEXT.**` line
- Keep the `---` separator after the block
- Levels: `strict` (agent checks compliance before every action), `normal` (standard), `off` (advisory only)
