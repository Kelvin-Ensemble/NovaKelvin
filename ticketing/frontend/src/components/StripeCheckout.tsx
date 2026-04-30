import React, { useState, useEffect } from 'react';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Check, Download, Mail, Loader2 } from 'lucide-react';

// Replace with your actual Stripe publishable key
const stripePromise = loadStripe('pk_test_YOUR_PUBLISHABLE_KEY');

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
  const [pollCount, setPollCount] = useState(0);

  // Poll for order confirmation
  const pollOrderStatus = async () => {
    try {
      const response = await fetch(`/api/tickets/order-status/?session_id=${sessionId}`);
      const data: OrderStatus = await response.json();

      if (data.status === 'confirmed') {
        setOrderDetails(data);
        setStatus('complete');
        return true; // Stop polling
      } else if (data.status === 'failed') {
        setStatus('error');
        return true; // Stop polling
      }

      return false; // Continue polling
    } catch (error) {
      console.error('Error polling order status:', error);
      return false; // Continue polling
    }
  };

  // Start polling when status changes to 'confirming'
  useEffect(() => {
    if (status !== 'confirming') return;

    const interval = setInterval(async () => {
      setPollCount(prev => prev + 1);
      const shouldStop = await pollOrderStatus();

      if (shouldStop) {
        clearInterval(interval);
      }

      // Timeout after 30 seconds (30 polls at 1 second each)
      if (pollCount >= 30) {
        clearInterval(interval);
        setStatus('error');
      }
    }, 1000); // Poll every second

    // Initial poll
    pollOrderStatus();

    return () => clearInterval(interval);
  }, [status, pollCount, sessionId]);

  const options = {
    clientSecret,
    onComplete: () => {
      // Payment completed in Stripe, now wait for webhook
      setStatus('confirming');
      setPollCount(0);
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
              Please check your email or contact <a href="mailto:webmaster@kelvin-ensemle.co.uk">webmaster@kelvin-ensemble.co.uk</a> with session ID:
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
          <EmbeddedCheckoutProvider stripe={stripePromise} options={options}>
            <EmbeddedCheckout />
          </EmbeddedCheckoutProvider>
        </div>
      </CardContent>
    </Card>
  );
};