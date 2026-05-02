import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || 'AIzaSyB_YVhUOJ9vqGxECfoblbSQ-C3J8OjnCxw',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || 'timi-childern-stories.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'timi-childern-stories',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || 'timi-childern-stories.firebasestorage.app',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '839918420419',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '1:839918420419:web:977870986209404eebbd76',
};

// DEBUG: Remove after verifying Firebase config reaches browser
console.log('Firebase config:', { ...firebaseConfig, apiKey: firebaseConfig.apiKey });

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app);

export { app, auth, db, storage };
