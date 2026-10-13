import { create } from "zustand";
import { useToasts } from "@/components/Game/Toasts";
import { account, authToken, profileApi, setAuthToken, type Profile, type UserInfo } from "@/lib/api";
import { translate } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { setTileBack, type TileBack } from "@/lib/tilePainter";
import { CircleCheck, Trophy } from "lucide-react";

/** A progression event pushed by the server after a hand (backend/progression.py). */
export interface ProgressEvent {
  type: "XP" | "LEVEL_UP" | "MISSION_DONE" | "ACHIEVEMENT" | "MATCH_REWARD" | "STATE";
  [key: string]: unknown;
}

interface AccountState {
  user: UserInfo | null;
  profile: Profile | null;
  loaded: boolean;
  lastXp: number;
  /** level and experience before the latest hand's rewards, so the result can grow the bar */
  xpBefore: { level: number; xp: number; xp_next: number } | null;
  resetHandRewards: () => void;
  /** set by a LEVEL_UP event; LevelUpShow plays the full-screen moment and clears it */
  levelUp: { level: number; coins: number } | null;
  clearLevelUp: () => void;
  load: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  applyProgress: (events: ProgressEvent[]) => void;
  signIn: (token: string, user: UserInfo) => void;
  signOut: () => void;
}

function applyCosmetics(profile: Profile) {
  setTileBack((profile.equipped.tile_back ?? "jade") as TileBack);
}

let loading: Promise<void> | null = null;

export const useAccount = create<AccountState>((set, get) => ({
  user: null,
  profile: null,
  loaded: false,
  lastXp: 0,
  xpBefore: null,
  resetHandRewards: () => set({ lastXp: 0, xpBefore: null }),
  levelUp: null,
  clearLevelUp: () => set({ levelUp: null }),
  load: () => {
    // every visitor gets a (guest) account so levels, missions and coins always work
    loading ??= (async () => {
      try {
        if (!authToken()) {
          const g = await account.guest();
          setAuthToken(g.token);
          set({ user: g.user });
        } else {
          set({ user: await account.me() });
        }
        await get().refreshProfile();
      } catch {
        setAuthToken(null);
        set({ user: null, profile: null });
      } finally {
        set({ loaded: true });
        loading = null;
      }
    })();
    return loading;
  },
  refreshProfile: async () => {
    try {
      const profile = await profileApi.me();
      applyCosmetics(profile);
      set({ profile, user: profile.user });
    } catch {
      /* offline or signed out */
    }
  },
  applyProgress: (events) => {
    const push = useToasts.getState().push;
    let gained = 0;
    for (const e of events) {
      switch (e.type) {
        case "XP":
          gained += Number(e.xp);
          break;
        case "LEVEL_UP":
          sfx.levelUp();
          set({ levelUp: { level: Number(e.level), coins: Number(e.coins) } });
          break;
        case "MISSION_DONE":
          push({ icon: CircleCheck, tone: "green", title: translate("任務完成：{name}", { name: String(e.name) }),
            body: translate("到大廳領取 {n} 金幣", { n: Number(e.coins) }) });
          break;
        case "ACHIEVEMENT":
          push({ icon: Trophy, tone: "gold", title: translate("成就解鎖：{name}", { name: String(e.name) }),
            body: translate("+{n} 金幣", { n: Number(e.coins) }) });
          break;
        case "MATCH_REWARD":
          gained += Number(e.xp);
          break;
        case "STATE": {
          const prof = get().profile;
          if (prof) {
            set({ xpBefore: { level: prof.level, xp: prof.xp, xp_next: prof.xp_next } });
            set({ profile: { ...prof, level: Number(e.level), xp: Number(e.xp),
              xp_next: Number(e.xp_next), coins: Number(e.coins) } });
          }
          break;
        }
      }
    }
    if (gained) set({ lastXp: gained });
    void get().refreshProfile(); // mission progress and achievements
  },
  signIn: (token, user) => {
    setAuthToken(token);
    set({ user, loaded: true });
    void get().refreshProfile();
  },
  signOut: () => {
    setAuthToken(null);
    set({ user: null, profile: null, loaded: false });
    void get().load();
  },
}));
