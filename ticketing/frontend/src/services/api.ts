import { Concert, TicketType } from '../types';

const API_BASE = '/api/tickets';

interface CheckoutLineItem {
  // A TicketType primary key, or a bare Stripe price ID for donations.
  ticket_type_id: number | string;
  quantity: number;
}

interface CheckoutSession {
  client_secret: string;
  session_id: string;
}

export const api = {
  async getConcerts(): Promise<Concert[]> {
    const response = await fetch(`${API_BASE}/concerts/`);
    if (!response.ok) throw new Error('Failed to fetch concerts');
    return response.json();
  },

  async getTicketTypes(concertId: number): Promise<TicketType[]> {
    const response = await fetch(`${API_BASE}/concert/tickettypes?concert_id=${concertId}`);
    if (!response.ok) throw new Error('Failed to fetch ticket types');
    return response.json();
  },

  async createCheckoutSession(concertId: number, lineItems: CheckoutLineItem[]): Promise<CheckoutSession> {
    const response = await fetch(`${API_BASE}/create-checkout-session/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        concert_id: concertId,
        line_items: lineItems,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create checkout session');
    }

    return response.json();
  },
};