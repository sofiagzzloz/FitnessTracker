const REMOTE_BACKEND = "https://fitness-backend.redglacier-88610d81.eastus.azurecontainerapps.io";

const isBrowser = typeof window !== "undefined";
const isLocalHost =
	isBrowser &&
	["localhost", "127.0.0.1"].includes(window.location.hostname);

const localBase = isBrowser ? window.location.origin : REMOTE_BACKEND;

export const API_BASE = isLocalHost ? localBase : REMOTE_BACKEND;
