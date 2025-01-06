import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { setCookie } from '../../utils/cookies';

export default function ChatRedirect() {
  const router = useRouter();
  const { id } = router.query;

  useEffect(() => {
    if (id && typeof id === 'string') {
      setCookie('initial_chat_id', id);
      router.push('/');
    }
  }, [id, router]);

  return null;
} 