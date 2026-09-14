import React, { useState, useEffect } from 'react';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Check, Download, Mail, Loader2 } from 'lucide-react';

// The publishable key is rendered onto the mount point by ticket_purchase.html.
let stripePromise: ReturnType<typeof loadStripe> | null = null;

const getStripe = () => {
  if (!stripePromise) {
    const key = document.getElementById('ticketing-root')?.dataset.stripePublishableKey;

    if (!key) {
      console.error('Missing data-stripe-publishable-key on #ticketing-root');
      return null;
    }

    stripePromise = loadStripe(key);
  }

  return stripePromise;
};

const POLL_INTERVAL_MS = 1000;
const MAX_POLL_ATTEMPTS = 30;

interface StripeCheckoutProps {
  clientSecret: string;
  sessionId: string;
  onBack: () => void;
  onComplete: () => void;
  concertName: string;
}

interface OrderStatus {
  status: 'pending' | 'confirmed' | 'failed';
  order_id?: number;
  customer_email?: string;
  customer_name?: string;
  concert_name?: string;
  total_amount?: string;
  currency?: string;
}

export const StripeCheckout: React.FC<StripeCheckoutProps> = ({
  clientSecret,
  sessionId,
  onBack,
  onComplete,
  concertName
}) => {
  const [status, setStatus] = useState<'checkout' | 'confirming' | 'complete' | 'error'>('checkout');
  const [orderDetails, setOrderDetails] = useState<OrderStatus | null>(null);

  // Poll the order status once the payment lands, until the webhook confirms it.
  useEffect(() => {
    if (status !== 'confirming') return;

    let cancelled = false;
    let attempts = 0;
    let timeout: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      attempts += 1;

      try {
        const response = await fetch(
          `/api/tickets/order-status/?session_id=${encodeURIComponent(sessionId)}`
        );
        const data: OrderStatus = await response.json();

        if (cancelled) return;

        if (data.status === 'confirmed') {
          setOrderDetails(data);
          setStatus('complete');
          return;
        }

        if (data.status === 'failed') {
          setStatus('error');
          return;
        }
      } catch (error) {
        console.error('Error polling order status:', error);
      }

      if (cancelled) return;

      if (attempts >= MAX_POLL_ATTEMPTS) {
        setStatus('error');
        return;
      }

      timeout = setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();

    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, [status, sessionId]);

  const options = {
    clientSecret,
    onComplete: () => {
      // Payment completed in Stripe, now wait for webhook
      setStatus('confirming');
    },
  };

  if (status === 'error') {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="mb-4">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">Order Confirmation Issue</h3>
            <p className="text-gray-600 mb-6">
              We're having trouble confirming your order. Your payment may have been processed.
              Please check your email or contact <a href="mailto:webmaster@kelvin-symphony.co.uk">webmaster@kelvin-symphony.co.uk</a> with session ID:
              <span className="font-mono text-sm block mt-2">{sessionId.substring(0, 20)}...</span>
            </p>
            <Button onClick={onBack}>Back to Tickets</Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (status === 'confirming') {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="mb-4">
            <Loader2 className="w-16 h-16 text-[#008888] animate-spin mx-auto mb-4" />
            <h3 className="text-2xl font-bold text-gray-900 mb-2">Confirming Your Order</h3>
            <p className="text-gray-600">
              Payment successful! We're finalizing your ticket reservation...
            </p>
            <p className="text-sm text-gray-500 mt-4">This usually takes just a few seconds</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (status === 'complete' && orderDetails) {
    return (
      <Card>
        <CardContent className="p-12">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-4">
              <Check className="w-12 h-12 text-green-600" />
            </div>
            <h3 className="text-3xl font-bold text-gray-900 mb-2">Order Confirmed!</h3>
            <p className="text-lg text-gray-600">Your tickets have been reserved</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-6 mb-6">
            <h4 className="font-semibold text-gray-900 mb-3 text-lg">Order Details</h4>
            <div className="space-y-2 text-gray-700">
              <div className="flex justify-between">
                <span>Order ID:</span>
                <span className="font-mono text-sm">#{orderDetails.order_id}</span>
              </div>
              {orderDetails.total_amount && (
                <div className="flex justify-between">
                  <span>Total:</span>
                  <span className="font-medium">
                    {orderDetails.currency === 'GBP' ? '£' : orderDetails.currency}
                    {orderDetails.total_amount}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-start">
              <Mail className="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
              <div>
                <p className="text-sm text-blue-900">
                  <strong>Confirmation email sent to:</strong>
                </p>
                <p className="text-sm text-blue-800 mt-1">{orderDetails.customer_email}</p>
                <p className="text-xs text-blue-700 mt-2">
                  Your tickets and receipt have been emailed. Please check your inbox and spam folder.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <Button
              onClick={onComplete}
              className="w-full"
            >
              Book More Tickets
            </Button>
            <Button
              onClick={() => window.print()}
              variant="outline"
              className="w-full"
            >
              <Download className="w-4 h-4 mr-2" />
              Print Confirmation
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Complete Your Purchase</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <Button
            onClick={onBack}
            variant="outline"
            className="mb-4"
          >
            ← Back to Tickets
          </Button>
        </div>

        <div id="checkout">
          <EmbeddedCheckoutProvider stripe={getStripe()} options={options}>
            <EmbeddedCheckout />
          </EmbeddedCheckoutProvider>
        </div>
      </CardContent>
    </Card>
  );
};