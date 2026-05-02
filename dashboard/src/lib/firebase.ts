import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: 'AIzaSyB_YVhUOJ9vqGxECfoblbSQ-C3J8OjnCxw',
  authDomain: 'timi-childern-stories.firebaseapp.com',
  projectId: 'timi-childern-stories',
  storageBucket: 'timi-childern-stories.firebasestorage.app',
  messagingSenderId: '839918420419',
  appId: '1:839918420419:web:977870986209404eebbd76',
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app);

export { app, auth, db, storage };
