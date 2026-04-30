import React from 'react';
import { Concert, TicketType, TicketQuantities } from '../types';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';

interface OrderSummaryProps {
  concert: Concert | null;
  ticketTypes: TicketType[];
  ticketQuantities: TicketQuantities;
  donationAmount?: number;
}

export const OrderSummary: React.FC<OrderSummaryProps> = ({
  concert,
  ticketTypes,
  ticketQuantities,
  donationAmount = 0
}) => {
  const getTotalTickets = () => {
    return Object.values(ticketQuantities).reduce((sum, qty) => sum + qty, 0);
  };

  const calculateTicketsTotal = () => {
    return ticketTypes.reduce((sum, tier) => {
      return sum + (tier.price * (ticketQuantities[tier.id] || 0));
    }, 0);
  };

  const calculateGrandTotal = () => {
    return calculateTicketsTotal() + donationAmount;
  };

  return (
    <Card className="sticky top-24">
      <CardHeader>
        <CardTitle>Order Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {concert && (
          <div>
            <h4 className="font-semibold text-gray-900 mb-2">Concert</h4>
            <p className="text-sm text-gray-600">{concert.concert_name}</p>
            <p className="text-sm text-gray-600">{concert.concert_date}</p>
          </div>
        )}

        {getTotalTickets() > 0 && (
          <div>
            <h4 className="font-semibold text-gray-900 mb-2">Tickets</h4>
            {ticketTypes.map((t_type) => (
              ticketQuantities[t_type.id] > 0 && (
                <div key={t_type.id} className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>{t_type.ticket_label} × {ticketQuantities[t_type.id]}</span>
                  <span>£{(t_type.price * ticketQuantities[t_type.id]).toFixed(2)}</span>
                </div>
              )
            ))}
            <div className="text-sm text-gray-600 mt-2 pt-2 border-t">
              Total Tickets: {getTotalTickets()}
            </div>
          </div>
        )}

        <div className="border-t pt-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-gray-600">Subtotal</span>
            <span className="font-semibold">£{calculateTicketsTotal().toFixed(2)}</span>
          </div>
          {donationAmount > 0 && (
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-600">Donation</span>
              <span className="font-semibold">£{donationAmount.toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between items-center text-lg font-bold pt-2 border-t">
            <span>Total</span>
            <span className="text-[#008888]">£{calculateGrandTotal().toFixed(2)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};