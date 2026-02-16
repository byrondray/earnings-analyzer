const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

let clerkInstance = null;
let _resolveReady;
const clerkReady = new Promise((resolve) => {
  _resolveReady = resolve;
});

export async function initClerk() {
  if (clerkInstance) return clerkInstance;

  if (!PUBLISHABLE_KEY) {
    console.warn('VITE_CLERK_PUBLISHABLE_KEY not set — auth disabled');
    _resolveReady();
    return null;
  }

  try {
    const ClerkModule = await import('@clerk/clerk-js');
    const Clerk = ClerkModule.Clerk || ClerkModule.default;
    clerkInstance = new Clerk(PUBLISHABLE_KEY);
    await clerkInstance.load();
    _resolveReady();
    return clerkInstance;
  } catch (err) {
    console.error('Failed to load Clerk:', err);
    _resolveReady();
    return null;
  }
}

export function getClerk() {
  return clerkInstance;
}

export async function getToken() {
  await clerkReady;
  if (!clerkInstance?.session) return null;
  return clerkInstance.session.getToken();
}

export async function signIn() {
  await clerkReady;
  if (!clerkInstance) return;
  clerkInstance.openSignIn();
}

export async function signOut() {
  await clerkReady;
  if (!clerkInstance) return;
  await clerkInstance.signOut();
}

export function getUser() {
  return clerkInstance?.user ?? null;
}

export function isSignedIn() {
  return !!clerkInstance?.user;
}
