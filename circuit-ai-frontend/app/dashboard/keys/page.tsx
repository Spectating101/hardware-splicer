'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { motion } from 'framer-motion';
import { Key, Plus, Copy, Check, Trash2, Eye, EyeOff, Calendar, Activity } from 'lucide-react';

interface APIKey {
  id: string;
  name: string;
  key: string;
  created_at: string;
  last_used?: string;
  usage_count: number;
  is_active: boolean;
}

export default function APIKeysPage() {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  // Mock data - replace with actual API calls
  useEffect(() => {
    setApiKeys([
      {
        id: 'key_1',
        name: 'Development Key',
        key: 'ckt_live_1234567890abcdef',
        created_at: '2024-01-15T10:30:00Z',
        last_used: '2024-01-20T14:22:00Z',
        usage_count: 1250,
        is_active: true
      },
      {
        id: 'key_2',
        name: 'Production Key',
        key: 'ckt_live_fedcba0987654321',
        created_at: '2024-01-10T09:15:00Z',
        last_used: '2024-01-20T16:45:00Z',
        usage_count: 5670,
        is_active: true
      }
    ]);
  }, []);

  const createAPIKey = async () => {
    if (!newKeyName.trim()) return;

    setIsCreating(true);
    try {
      // Mock API call
      const newKey: APIKey = {
        id: `key_${Date.now()}`,
        name: newKeyName,
        key: `ckt_live_${Math.random().toString(36).substring(2, 15)}`,
        created_at: new Date().toISOString(),
        usage_count: 0,
        is_active: true
      };

      setApiKeys(prev => [newKey, ...prev]);
      setNewKeyName('');
    } catch (error) {
      console.error('Failed to create API key:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const copyToClipboard = (key: string, keyId: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const toggleKeyVisibility = (keyId: string) => {
    setVisibleKeys(prev => {
      const newSet = new Set(prev);
      if (newSet.has(keyId)) {
        newSet.delete(keyId);
      } else {
        newSet.add(keyId);
      }
      return newSet;
    });
  };

  const revokeAPIKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
      return;
    }

    try {
      // Mock API call
      setApiKeys(prev => prev.map(key => 
        key.id === keyId ? { ...key, is_active: false } : key
      ));
    } catch (error) {
      console.error('Failed to revoke API key:', error);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const maskKey = (key: string) => {
    return key.substring(0, 8) + '•'.repeat(16) + key.substring(key.length - 4);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">API Keys</h1>
              <p className="text-slate-600 mt-1">Manage your Circuit.AI API keys and access</p>
            </div>
	            <Button 
	              onClick={() => (document.getElementById('create-key-modal') as HTMLDialogElement | null)?.showModal()}
	              className="bg-blue-600 hover:bg-blue-700 text-white"
	            >
              <Plus className="w-4 h-4 mr-2" />
              Create API Key
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* API Keys List */}
        <div className="space-y-6">
          {apiKeys.map((apiKey) => (
            <motion.div
              key={apiKey.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className={`${!apiKey.is_active ? 'opacity-60' : ''}`}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-lg flex items-center justify-center">
                        <Key className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-slate-900">{apiKey.name}</CardTitle>
                        <CardDescription>
                          Created {formatDate(apiKey.created_at)}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        apiKey.is_active 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {apiKey.is_active ? 'Active' : 'Revoked'}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* API Key Display */}
                    <div>
                      <label className="text-sm font-medium text-slate-700 mb-2 block">
                        API Key
                      </label>
                      <div className="flex items-center space-x-2">
                        <Input
                          value={visibleKeys.has(apiKey.id) ? apiKey.key : maskKey(apiKey.key)}
                          readOnly
                          className="font-mono text-sm"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleKeyVisibility(apiKey.id)}
                        >
                          {visibleKeys.has(apiKey.id) ? (
                            <EyeOff className="w-4 h-4" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(apiKey.key, apiKey.id)}
                        >
                          {copiedKey === apiKey.id ? (
                            <Check className="w-4 h-4" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Usage Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-slate-50 p-4 rounded-lg">
                        <div className="flex items-center space-x-2 mb-2">
                          <Activity className="w-4 h-4 text-slate-600" />
                          <span className="text-sm font-medium text-slate-700">Usage Count</span>
                        </div>
                        <p className="text-2xl font-bold text-slate-900">{apiKey.usage_count.toLocaleString()}</p>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-lg">
                        <div className="flex items-center space-x-2 mb-2">
                          <Calendar className="w-4 h-4 text-slate-600" />
                          <span className="text-sm font-medium text-slate-700">Last Used</span>
                        </div>
                        <p className="text-sm text-slate-900">
                          {apiKey.last_used ? formatDate(apiKey.last_used) : 'Never'}
                        </p>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-lg">
                        <div className="flex items-center space-x-2 mb-2">
                          <Key className="w-4 h-4 text-slate-600" />
                          <span className="text-sm font-medium text-slate-700">Status</span>
                        </div>
                        <p className="text-sm text-slate-900">
                          {apiKey.is_active ? 'Active' : 'Revoked'}
                        </p>
                      </div>
                    </div>

                    {/* Actions */}
                    {apiKey.is_active && (
                      <div className="flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => revokeAPIKey(apiKey.id)}
                          className="text-red-600 border-red-200 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Revoke Key
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}

          {apiKeys.length === 0 && (
            <Card>
              <CardContent className="text-center py-12">
                <Key className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-900 mb-2">No API Keys</h3>
                <p className="text-slate-600 mb-4">
                  Create your first API key to start using the Circuit.AI API
                </p>
	                  <Button
	                    onClick={() => (document.getElementById('create-key-modal') as HTMLDialogElement | null)?.showModal()}
	                    className="bg-blue-600 hover:bg-blue-700 text-white"
	                  >
                  <Plus className="w-4 h-4 mr-2" />
                  Create API Key
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Create API Key Modal */}
      <dialog id="create-key-modal" className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">Create New API Key</h3>
          <div className="space-y-4">
            <div>
              <label className="label">
                <span className="label-text">Key Name</span>
              </label>
              <Input
                type="text"
                placeholder="e.g., Production Key, Development Key"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>Important:</strong> Your API key will be shown only once. Make sure to copy it and store it securely.
              </p>
            </div>
          </div>
          <div className="modal-action">
            <form method="dialog">
              <Button variant="outline" className="mr-2">Cancel</Button>
              <Button 
                onClick={createAPIKey}
                disabled={!newKeyName.trim() || isCreating}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                {isCreating ? 'Creating...' : 'Create Key'}
              </Button>
            </form>
          </div>
        </div>
      </dialog>
    </div>
  );
}
