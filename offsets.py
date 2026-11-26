from dataclasses import dataclass
import struct
from memory import Memory

# --- Паттерны (ваш код + добавленный dwViewAngles) ---
SCHEMA_SYSTEM_PATTERN = "4C 8D 35 ? ? ? ? 0F 28 45"
BUTTON_LIST_PATTERN = "48 8B 15 ? ? ? ? 48 85 D2 74 ? 48 8B 02 48 85 C0"

CLIENT_PATTERNS = {
    "dwPrediction": ("48 8D 05 ? ? ? ? C3 CC CC CC CC CC CC CC CC 40 53 56 41 54", "Rip", 3, 0, None),
    "dwViewMatrix": ("48 8D 0D ? ? ? ? 48 C1 E0 06", "Rip", 3, 0, None),
    "dwViewAngles": ("48 8B 0D ? ? ? ? 48 8B 01 48 FF 60 30", "Rip", 3, 0, None),  # добавлено
    "dwLocalPlayerPawn": ("4C 39 B6 ? ? ? ? 74 ? 44 88 BE", "Imm32", 3, 0, "dwPrediction"),
    "dwLocalPlayerController": ("48 8B 05 ? ? ? ? 41 89 BE", "Rip", 3, 0, None),
    "dwEntityList": ("48 89 0D ? ? ? ? E9 ? ? ? ? CC", "Rip", 3, 0, None),
    "dwGameRules": ("F6 C1 01 0F 85 ? ? ? ? 4C 8B 05 ? ? ? ? 4D 85", "Rip", 12, 0, None),
    "dwSensitivity": ("48 8D 0D ? ? ? ? 0F 57 C9 0F 28 F0", "Rip", 3, 8, None),
    "dwGlobalVars": ("48 89 15 ? ? ? ? 48 89 42", "Rip", 3, 0, None),
    "dwPlantedC4": ("48 8B 05 ? ? ? ? 45 32 C0 48 85 C0 74 ? 44 38 80", "Rip", 3, 0, None),
}


def ScanPattern(buffer: bytes, pattern: str) -> int:
    signature = [None if token in ("?", "??") else int(token, 16) for token in pattern.split()]
    chunks = []
    chunk_start = None
    for index, byte in enumerate(signature + [None]):
        if byte is not None and chunk_start is None:
            chunk_start = index
        elif byte is None and chunk_start is not None:
            chunks.append((chunk_start, bytes(signature[chunk_start:index])))
            chunk_start = None
    if not chunks:
        return -1
    anchor_offset, anchor = max(chunks, key=lambda c: len(c[1]))
    search_from = anchor_offset
    while True:
        found = buffer.find(anchor, search_from)
        if found < 0:
            return -1
        start = found - anchor_offset
        if start + len(signature) > len(buffer):
            return -1
        if start >= 0 and all(buffer[start + off:start + off + len(chunk)] == chunk for off, chunk in chunks):
            return start
        search_from = found + 1


def Extract(buffer: bytes, index: int, kind: str, position: int, extra: int = 0) -> int:
    if kind == "Rip":
        return index + position + 4 + struct.unpack_from("<i", buffer, index + position)[0] + extra
    return (struct.unpack_from("<I", buffer, index + position)[0] + extra) & 0xFFFFFFFF


def DumpOffsets(mem: Memory, client_base: int, client_buffer: bytes) -> dict:
    result = {"dwSensitivity_sensitivity": 0x58}
    for name, (pattern, kind, position, extra, parent) in CLIENT_PATTERNS.items():
        index = ScanPattern(client_buffer, pattern)
        if index < 0 or (parent and parent not in result):
            print(f"[!] Pattern not found: {name}")
            continue
        result[name] = result.get(parent, 0) + Extract(client_buffer, index, kind, position, extra)
    return result


def DumpButtons(mem: Memory, client_base: int, client_buffer: bytes) -> dict:
    result = {}
    index = ScanPattern(client_buffer, BUTTON_LIST_PATTERN)
    if index < 0:
        print("[!] Pattern not found: ButtonList")
        return result
    button_pointer = mem.read_pointer(client_base + Extract(client_buffer, index, "Rip", 3))
    visited = set()
    while button_pointer and button_pointer not in visited:
        visited.add(button_pointer)
        try:
            button_data = mem.read(button_pointer, 0x90)
            name = mem.read_string(struct.unpack_from("<Q", button_data, 0x08)[0], 32)
            if button_pointer + 0x30 >= client_base:
                result[name] = button_pointer + 0x30 - client_base
            button_pointer = struct.unpack_from("<Q", button_data, 0x88)[0]
        except Exception as e:
            print(f"[!] Failed to read button at 0x{button_pointer:X}: {e}")
            break
    return result


def ReadHashElements(mem: Memory, hash_address: int) -> list[int]:
    elements = []
    header = mem.read(hash_address, 0x1870)
    blocks_allocated, peak_allocated = struct.unpack_from("<ii", header, 0x0C)

    for bucket in range(256):
        node_pointer = struct.unpack_from("<Q", header, 0x60 + bucket * 0x18 + 0x10)[0]
        while node_pointer and len(elements) < blocks_allocated:
            next_pointer, data_pointer = struct.unpack_from(
                "<QQ", mem.read(node_pointer, 0x18), 0x08
            )
            if data_pointer:
                elements.append(data_pointer)
            node_pointer = next_pointer

    blob_pointer = struct.unpack_from("<Q", header, 0x20)[0]
    for _ in range(max(peak_allocated, 0)):
        if not blob_pointer:
            break
        blob_data = mem.read(blob_pointer, 0x18)
        if struct.unpack_from("<Q", blob_data, 0x10)[0]:
            elements.append(struct.unpack_from("<Q", blob_data, 0x10)[0])
        blob_pointer = struct.unpack_from("<Q", blob_data, 0)[0]

    return list(dict.fromkeys(elements))


def DumpSchemas(mem: Memory, schema_base: int, schema_size: int, module_name: str = "client.dll") -> dict:
    result = {}
    buffer = mem.read(schema_base, schema_size)
    index = ScanPattern(buffer, SCHEMA_SYSTEM_PATTERN)
    if index < 0:
        print("[!] Pattern not found: SchemaSystem")
        return result

    schema_system = mem.read(schema_base + Extract(buffer, index, "Rip", 3), 0x1A0)
    scope_count = min(max(struct.unpack_from("<i", schema_system, 0x190)[0], 0), 256)
    scopes_pointer = struct.unpack_from("<Q", schema_system, 0x198)[0]
    scopes = struct.unpack(f"<{scope_count}Q", mem.read(scopes_pointer, scope_count * 8))

    for scope_pointer in scopes:
        if not scope_pointer or mem.read_string(scope_pointer + 0x08, 256) != module_name:
            continue
        for class_pointer in ReadHashElements(mem, scope_pointer + 0x560):
            try:
                class_data = mem.read(class_pointer, 0x38)
                class_name = mem.read_string(struct.unpack_from("<Q", class_data, 0x08)[0], 128)
                field_count = struct.unpack_from("<h", class_data, 0x24)[0]
                fields_pointer = struct.unpack_from("<Q", class_data, 0x30)[0]

                fields = {}
                if field_count > 0 and fields_pointer:
                    field_data = mem.read(fields_pointer, field_count * 0x20)
                    for field in range(field_count):
                        field_name = mem.read_string(
                            struct.unpack_from("<Q", field_data, field * 0x20)[0], 128
                        )
                        fields[field_name] = struct.unpack_from(
                            "<i", field_data, field * 0x20 + 0x10
                        )[0]
                if class_name:
                    result[class_name] = fields
            except Exception as e:
                print(f"[!] Failed to read class at 0x{class_pointer:X}: {e}")
    return result


@dataclass
class Offset:
    dwViewMatrix: int
    dwViewAngles: int          # добавлено
    dwLocalPlayerPawn: int
    dwEntityList: int
    dwLocalPlayerController: int
    dwGameRules: int
    dwSensitivity_sensitivity: int
    dwSensitivity: int
    dwGlobalVars: int
    dwPlantedC4: int

    ButtonJump: int

    m_hPlayerPawn: int
    m_iHealth: int
    m_lifeState: int
    m_iTeamNum: int
    m_vOldOrigin: int
    m_pGameSceneNode: int
    m_modelState: int
    m_boneArray: int
    m_sSanitizedPlayerName: int
    m_iIDEntIndex: int
    m_flFlashMaxAlpha: int
    m_fFlags: int
    m_iFOV: int
    m_pCameraServices: int
    m_bIsScoped: int

    m_vecViewOffset: int
    m_entitySpottedState: int
    m_bSpotted: int
    m_bBombPlanted: int

    m_iShotsFired: int
    m_pAimPunchServices: int
    m_unpredictableBaseTick: int

    m_bSpottedByMask: int
    m_vecVelocity: int

    m_ArmorValue: int
    m_bIsDefusing: int
    m_pInGameMoneyServices: int
    m_iAccount: int
    m_pWeaponServices: int
    m_hActiveWeapon: int
    m_pItemServices: int
    m_bHasHelmet: int
    m_bHasDefuser: int
    m_AttributeManager: int
    m_Item: int
    m_iItemDefinitionIndex: int
    m_iFOVStart: int

    m_designerName: int
    m_nSmokeEffectTickBegin: int
    m_bDidSmokeEffect: int
    m_vSmokeDetonationPos: int
    m_flC4Blow: int
    m_bBombDefused: int
    m_angEyeAngles: int
    m_Glow: int
    m_iGlowType: int
    m_glowColorOverride: int
    m_bGlowing: int

def GetOffsets(mem: Memory) -> Offset:
    client_base = mem.client_base
    client_size = mem.get_module_size(client_base)
    schema_base = mem.schemasystem_base
    schema_size = mem.get_module_size(schema_base)

    client_buffer = mem.read(client_base, client_size)

    offsets = DumpOffsets(mem, client_base, client_buffer)
    buttons = DumpButtons(mem, client_base, client_buffer)
    schemas = DumpSchemas(mem, schema_base, schema_size)

    def lookup(data, *keys):
        try:
            for key in keys:
                data = data[key]
            return data
        except KeyError:
            print(f"[!] Offset not found: {' -> '.join(keys)}")
            exit(1)

    print(f"[+] Dumped {len(offsets)} offsets, {len(buttons)} buttons, {len(schemas)} schemas")

    def lookup_opt(data, *keys, default=0):
        try:
            for key in keys:
                data = data[key]
            return data
        except KeyError:
            return default

    return Offset(
        dwViewMatrix=lookup(offsets, "dwViewMatrix"),
        dwViewAngles=lookup(offsets, "dwViewAngles"),
        dwLocalPlayerPawn=lookup(offsets, "dwLocalPlayerPawn"),
        dwEntityList=lookup(offsets, "dwEntityList"),
        dwLocalPlayerController=lookup(offsets, "dwLocalPlayerController"),
        dwGameRules=lookup(offsets, "dwGameRules"),
        dwSensitivity_sensitivity=lookup(offsets, "dwSensitivity_sensitivity"),
        dwSensitivity=lookup(offsets, "dwSensitivity"),
        dwGlobalVars=lookup(offsets, "dwGlobalVars"),
        dwPlantedC4=lookup(offsets, "dwPlantedC4"),

        ButtonJump=lookup(buttons, "jump"),

        m_hPlayerPawn=lookup(schemas, "CCSPlayerController", "m_hPlayerPawn"),
        m_iHealth=lookup(schemas, "C_BaseEntity", "m_iHealth"),
        m_lifeState=lookup(schemas, "C_BaseEntity", "m_lifeState"),
        m_iTeamNum=lookup(schemas, "C_BaseEntity", "m_iTeamNum"),
        m_vOldOrigin=lookup(schemas, "C_BasePlayerPawn", "m_vOldOrigin"),
        m_pGameSceneNode=lookup(schemas, "C_BaseEntity", "m_pGameSceneNode"),
        m_modelState=lookup(schemas, "CSkeletonInstance", "m_modelState"),
        m_boneArray=128,
        m_sSanitizedPlayerName=lookup(schemas, "CCSPlayerController", "m_sSanitizedPlayerName"),
        m_iIDEntIndex=lookup(schemas, "C_CSPlayerPawn", "m_iIDEntIndex"),
        m_flFlashMaxAlpha=lookup(schemas, "C_CSPlayerPawnBase", "m_flFlashMaxAlpha"),
        m_fFlags=lookup(schemas, "C_BaseEntity", "m_fFlags"),
        m_iFOV=lookup(schemas, "CCSPlayerBase_CameraServices", "m_iFOV"),
        m_pCameraServices=lookup(schemas, "C_BasePlayerPawn", "m_pCameraServices"),
        m_bIsScoped=lookup(schemas, "C_CSPlayerPawn", "m_bIsScoped"),

        m_vecViewOffset=lookup(schemas, "C_BaseModelEntity", "m_vecViewOffset"),
        m_entitySpottedState=lookup(schemas, "C_CSPlayerPawn", "m_entitySpottedState"),
        m_bSpotted=lookup(schemas, "EntitySpottedState_t", "m_bSpotted"),
        m_bBombPlanted=lookup(schemas, "C_CSGameRules", "m_bBombPlanted"),

        m_iShotsFired=lookup(schemas, "C_CSPlayerPawn", "m_iShotsFired"),
        m_pAimPunchServices=lookup(schemas, "C_CSPlayerPawn", "m_pAimPunchServices"),
        m_unpredictableBaseTick=lookup(schemas, "CCSPlayer_AimPunchServices", "m_unpredictableBaseTick"),

        m_bSpottedByMask=lookup(schemas, "EntitySpottedState_t", "m_bSpottedByMask"),
        m_vecVelocity=lookup(schemas, "C_BaseEntity", "m_vecVelocity"),

        m_ArmorValue=lookup(schemas, "C_CSPlayerPawn", "m_ArmorValue"),
        m_bIsDefusing=lookup(schemas, "C_CSPlayerPawn", "m_bIsDefusing"),
        m_pInGameMoneyServices=lookup(schemas, "CCSPlayerController", "m_pInGameMoneyServices"),
        m_iAccount=lookup(schemas, "CCSPlayerController_InGameMoneyServices", "m_iAccount"),
        m_pWeaponServices=lookup(schemas, "C_BasePlayerPawn", "m_pWeaponServices"),
        m_hActiveWeapon=lookup(schemas, "CPlayer_WeaponServices", "m_hActiveWeapon"),
        m_pItemServices=lookup(schemas, "C_BasePlayerPawn", "m_pItemServices"),
        m_bHasHelmet=lookup(schemas, "CCSPlayer_ItemServices", "m_bHasHelmet"),
        m_bHasDefuser=lookup(schemas, "CCSPlayer_ItemServices", "m_bHasDefuser"),
        m_AttributeManager=lookup(schemas, "C_EconEntity", "m_AttributeManager"),
        m_Item=lookup(schemas, "C_AttributeContainer", "m_Item"),
        m_iItemDefinitionIndex=lookup(schemas, "C_EconItemView", "m_iItemDefinitionIndex"),
        m_iFOVStart=lookup(schemas, "CCSPlayerBase_CameraServices", "m_iFOVStart"),

        m_designerName=lookup(schemas, "CEntityIdentity", "m_designerName"),
        m_nSmokeEffectTickBegin=lookup(schemas, "C_SmokeGrenadeProjectile", "m_nSmokeEffectTickBegin"),
        m_bDidSmokeEffect=lookup(schemas, "C_SmokeGrenadeProjectile", "m_bDidSmokeEffect"),
        m_vSmokeDetonationPos=lookup(schemas, "C_SmokeGrenadeProjectile", "m_vSmokeDetonationPos"),
        m_flC4Blow=lookup(schemas, "C_PlantedC4", "m_flC4Blow"),
        m_bBombDefused=lookup(schemas, "C_PlantedC4", "m_bBombDefused"),
        m_angEyeAngles=lookup_opt(schemas, "C_CSPlayerPawn", "m_angEyeAngles"),
        m_Glow=lookup_opt(schemas, "C_BaseModelEntity", "m_Glow"),
        m_iGlowType=lookup_opt(schemas, "CGlowProperty", "m_iGlowType"),
        m_glowColorOverride=lookup_opt(schemas, "CGlowProperty", "m_glowColorOverride"),
        m_bGlowing=lookup_opt(schemas, "CGlowProperty", "m_bGlowing"),
    )